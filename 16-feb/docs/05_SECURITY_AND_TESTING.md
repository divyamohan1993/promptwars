# Security Model & Testing Strategy

## Security Architecture

QuestForge implements defense-in-depth security across every layer of the stack.

---

## Layer 1: Container Security

### Non-Root Execution
```dockerfile
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser
USER appuser
```
- Dedicated non-root user with no login shell
- Application files owned by `appuser`
- Minimal attack surface — no dev tools, no test files in production image

### Multi-Stage Build
```dockerfile
FROM python:3.12-slim AS builder     # Install dependencies
FROM python:3.12-slim                # Runtime only
COPY --from=builder /install /usr/local
```
- Build dependencies never reach the production image
- Only `app/` directory is copied (no tests, no configs, no docs)
- `python:3.12-slim` — minimal base image

---

## Layer 2: HTTP Security Headers

Every response includes OWASP-recommended security headers:

```python
class SecurityHeadersMiddleware:
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        h = response.headers
        h["X-Content-Type-Options"]  = "nosniff"
        h["X-Frame-Options"]        = "DENY"
        h["X-XSS-Protection"]       = "1; mode=block"
        h["Referrer-Policy"]        = "strict-origin-when-cross-origin"
        h["Permissions-Policy"]     = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
        h["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: blob: https://storage.googleapis.com; "
            "connect-src 'self'; "
            "font-src 'self' https://fonts.gstatic.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
```

| Header | Protection |
|--------|------------|
| CSP | Prevents XSS by restricting script/style/font sources |
| X-Frame-Options: DENY | Prevents clickjacking |
| HSTS | Forces HTTPS for 1 year |
| Permissions-Policy | Disables camera, mic, geolocation, payment, USB |
| Referrer-Policy | Limits referrer leakage |
| X-Content-Type-Options | Prevents MIME-type sniffing |

---

## Layer 3: Rate Limiting

Per-IP sliding-window rate limiter with bounded memory:

```python
class RateLimitMiddleware:
    _MAX_TRACKED_IPS = 10_000

    def __init__(self, app, max_requests=60, window_seconds=60):
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request, call_next):
        # Skip static assets and health probes
        # Prune expired timestamps for this IP
        # Check if limit exceeded -> 429 with Retry-After header
        # Evict oldest IPs if tracking > 10,000 unique clients
```

### Design Decisions
- **Sliding window**: More accurate than fixed windows, prevents burst at window boundaries
- **Memory bounded**: Max 10,000 tracked IPs with FIFO eviction — prevents OOM from DDoS
- **Static asset bypass**: CSS/JS/images skip rate limiting for performance
- **Health probe bypass**: `/api/health` is never rate-limited (Cloud Run needs it)
- **Configurable**: `RATE_LIMIT_PER_MINUTE` env var (default: 60)

---

## Layer 4: Input Validation

### API Boundary (Pydantic)
```python
class GameStartRequest(BaseModel):
    player_name: str = Field(..., min_length=1, max_length=50)
    adventure: Adventure  # Enum — only 4 valid values accepted

    @field_validator("player_name")
    def _sanitise_player_name(cls, v):
        v = v.strip()
        if not re.match(r"^[^\x00-\x08\x0b\x0c\x0e-\x1f]*$", v):
            raise ValueError("Player name contains invalid characters")
        return v

class ActionRequest(BaseModel):
    game_id: str = Field(..., min_length=1, max_length=128)
    action: str = Field(..., min_length=1, max_length=500)
```

### Prompt Injection Defense
```python
safe_action = player_action[:500]  # Hard truncation before injection into prompt
```

### AI Output Clamping
```python
_MAX_HEALTH_DELTA = 20
health_delta = max(-_MAX_HEALTH_DELTA, min(_MAX_HEALTH_DELTA, raw_delta))
choices = choices[:4]        # Max 4 choices
new_items = items[:5]        # Max 5 items added per turn
```

---

## Layer 5: Secrets Management

- **Zero secrets in code** — all credentials via environment variables
- **`.env.example`** — template file with placeholder values
- **`.gitignore`** — excludes `.env` from version control
- **Cloud Build substitutions** — secrets injected at deployment time
- **Swagger/ReDoc disabled** — `docs_url=None, redoc_url=None` prevents API documentation exposure in production

---

## Layer 6: XSS Prevention

### Server-Side
- CSP `script-src 'self'` — no inline scripts allowed
- CSP `style-src 'self' 'unsafe-inline'` — styles from same origin only (plus inline for dynamic styling)

### Client-Side
```javascript
escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;      // textContent auto-escapes HTML entities
    return div.innerHTML;
}
```
All user-provided and AI-generated text is HTML-escaped before DOM insertion.

---

## Testing Strategy

### Test Suite Structure
```
tests/
    conftest.py               # Shared fixtures (mock Gemini, test engine, async client)
    test_config.py            # Settings validation and parsing
    test_game_engine.py       # Core game logic (14,597 bytes — largest test file)
    test_middleware.py         # Security headers, rate limiting, request logging
    test_models.py            # Pydantic schema validation (8,862 bytes)
    test_routes.py            # API endpoint integration tests
    test_imagen_service.py    # Imagen service unit tests
    test_translate_service.py # Translate service unit tests
```

### Test Fixtures (conftest.py)
```python
@pytest.fixture
def mock_gemini_response():
    return {
        "narrative": "You find yourself in a dark, enchanted forest.",
        "choices": ["Follow the path", "Climb a tree", "Search the ground"],
        "health_delta": 0,
        "new_items": ["rusty sword"],
        ...
    }

@pytest.fixture
def mock_gemini_service(mock_gemini_response):
    service = AsyncMock(spec=GeminiService)
    service.generate_opening.return_value = mock_gemini_response
    service.generate_response.return_value = mock_gemini_response
    return service

@pytest.fixture
def game_engine(mock_gemini_service):
    return GameEngine(gemini_service=mock_gemini_service)

@pytest.fixture
async def client(app_with_engine):
    transport = ASGITransport(app=app_with_engine)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
```

### Test Categories

**Model Validation Tests** (`test_models.py`):
- Valid/invalid player names
- Control character rejection
- Field length constraints
- Enum validation (Adventure types)
- Default values and optional fields

**Game Engine Tests** (`test_game_engine.py`):
- Game creation flow
- Action processing
- Health clamping (boundaries at 0 and 100)
- Inventory add/remove logic
- Achievement triggering
- Map node creation and bi-directional linking
- Game over detection (death and completion)
- Firestore persistence (save/load/fallback)
- In-memory cache eviction

**Route Tests** (`test_routes.py`):
- HTTP status codes for all endpoints
- Request validation error responses
- Game not found (404)
- Game over action attempt (400)
- Dependency injection overrides

**Middleware Tests** (`test_middleware.py`):
- Security header presence and values
- Rate limit enforcement
- Static asset bypass
- Health probe bypass
- Request logging with Cloud Trace headers

**Service Tests**:
- Imagen: prompt construction, safety filters, error handling
- Translate: caching, thread offloading, graceful failure

### How Tests Run in CI
```yaml
# Cloud Build Step 1
- name: 'python:3.12-slim'
  entrypoint: bash
  args:
    - '-c'
    - |
      pip install -q -r requirements.txt -r requirements-dev.txt
      python -m pytest tests/ -q --tb=short
```

Tests gate the deployment — a failure in any test aborts the entire Cloud Build pipeline.
