# Google Services Integration

## Overview: 8 Google Cloud Services

QuestForge integrates **8 distinct Google Cloud services**, each serving a specific role in the application lifecycle. The integration follows a consistent pattern: feature-toggled, lazy-initialized singletons with graceful degradation.

```
+------------------------------------------------------------------+
|                    Google Cloud Platform                          |
|                                                                  |
|  +-----------+  +-----------+  +-----------+  +-----------+      |
|  |  Gemini   |  | Firestore |  | Cloud TTS |  | Translate |      |
|  |    API    |  |  (NoSQL)  |  |  (Audio)  |  |   (i18n)  |      |
|  +-----------+  +-----------+  +-----------+  +-----------+      |
|                                                                  |
|  +-----------+  +-----------+  +-----------+  +-----------+      |
|  |  Vertex   |  |   Cloud   |  |   Cloud   |  | Artifact  |      |
|  |  Imagen   |  |  Storage  |  |    Run    |  | Registry  |      |
|  +-----------+  +-----------+  +-----------+  +-----------+      |
|                                                                  |
|  +-----------------------------------------------------------+  |
|  |                    Cloud Build (CI/CD)                     |  |
|  +-----------------------------------------------------------+  |
|                                                                  |
|  +-----------------------------------------------------------+  |
|  |                  Cloud Logging (Observability)              |  |
|  +-----------------------------------------------------------+  |
+------------------------------------------------------------------+
```

---

## 1. Google Gemini API (Core)

**Role**: AI narrative engine — the brain of QuestForge

**Service**: `app/services/gemini_service.py`
**Model**: `gemini-3-flash-preview`
**SDK**: `google-generativeai`

### How It's Used
- Generates opening narratives for new adventures
- Produces contextual story continuations based on player actions
- Returns structured JSON with narrative text, choices, health changes, items, scene metadata, and map updates
- Maintains multi-turn coherence via compressed history context

### Technical Details
```python
genai.configure(api_key=settings.google_api_key)
model = genai.GenerativeModel(
    model_name="gemini-3-flash-preview",
    system_instruction=SYSTEM_PROMPT,  # 75-line DM prompt
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",  # Structured output
        temperature=0.9,                         # High creativity
    ),
)
response = await model.generate_content_async(prompt)
```

### Key Design Choices
- **Async API calls** (`generate_content_async`) — non-blocking I/O
- **Structured JSON output** — deterministic parsing for game state
- **System instruction** — persistent persona across all calls (dungeon master)
- **High temperature (0.9)** — creative narratives constrained by JSON schema
- **Fallback response** — pre-written scene returned on any API error

---

## 2. Cloud Firestore (Persistence)

**Role**: Persistent game state storage — games survive container restarts

**Service**: `app/services/firestore_service.py`
**SDK**: `google-cloud-firestore` (AsyncClient)
**Toggle**: `ENABLE_FIRESTORE=true`

### How It's Used
- Saves full `GameState` as Firestore documents after each turn
- Loads game state on retrieval (memory-first, Firestore fallback)
- Enables game resumption across container instances

### Technical Details
```python
class FirestoreService:
    def __init__(self):
        self._db = AsyncClient(project=settings.gcp_project_id)
        self._collection = settings.firestore_collection  # "games"

    async def save_game(self, game_id: str, state: dict) -> None:
        await self._doc_ref(game_id).set(state)

    async def load_game(self, game_id: str) -> dict | None:
        doc = await self._doc_ref(game_id).get()
        return doc.to_dict() if doc.exists else None
```

### Key Design Choices
- **Async client** — native non-blocking Firestore operations
- **Document-per-game** — each game is a single document keyed by UUID
- **Write-through cache** — in-memory dict is always written first, Firestore is secondary
- **Failure tolerance** — Firestore errors are caught and logged, game continues from memory
- **Bounded in-memory cache** — max 5,000 games cached; oldest evicted via FIFO

### Degradation
When disabled: games are stored in-memory only. They are lost on container restart but the application remains fully functional.

---

## 3. Cloud Text-to-Speech (Accessibility)

**Role**: Converts narrative text to spoken audio — immersive and accessible

**Service**: `app/services/tts_service.py`
**SDK**: `google-cloud-texttospeech` (TextToSpeechAsyncClient)
**Toggle**: `ENABLE_TTS=true`

### How It's Used
- Player clicks "Listen" button on any narrative
- Backend synthesizes text to MP3 audio
- Returns base64-encoded audio to the browser
- Browser plays audio via `new Audio("data:audio/mp3;base64,...")`

### Technical Details
```python
class TTSService:
    def __init__(self):
        self._client = texttospeech.TextToSpeechAsyncClient()
        self._cache = OrderedDict()  # LRU cache, max 50 entries

    async def synthesize(self, text: str, language_code: str = "en-US") -> str:
        # Check cache first (SHA-256 key from language + text)
        # If miss: synthesize via Cloud TTS API
        # Store result in LRU cache
        # Return base64-encoded MP3
```

### Key Design Choices
- **Async client** — native non-blocking API calls
- **LRU in-memory cache** (50 entries) — avoids re-synthesizing identical text
- **SHA-256 cache keys** — deterministic, collision-resistant
- **Language-aware caching** — same text in different languages gets separate cache entries
- **NEUTRAL voice gender** — inclusive audio output

### Degradation
When disabled: the "Listen" button's request receives HTTP 503. The frontend handles this gracefully.

---

## 4. Cloud Translate (Internationalization)

**Role**: Multi-language narrative support — play in 8+ languages

**Service**: `app/services/translate_service.py`
**SDK**: `google-cloud-translate` (v2 REST client)
**Toggle**: `ENABLE_TRANSLATE=true`

### How It's Used
- Player selects a language from the header dropdown (EN, ES, FR, DE, JA, HI, PT, ZH)
- When "Listen" is clicked, the narrative is translated to the selected language before TTS
- Translation results are cached to avoid redundant API calls

### Technical Details
```python
class TranslateService:
    def __init__(self):
        self._client = translate.Client()
        self._cache = OrderedDict()  # LRU cache, max 100 entries

    async def translate_text(self, text, target_language, source_language="en"):
        # v2 client is synchronous — wrapped in asyncio.to_thread()
        result = await asyncio.to_thread(
            self._client.translate, text, target_language=target_language
        )
        return {"translated_text": result["translatedText"], ...}
```

### Key Design Choices
- **Thread offloading** — v2 client is sync, wrapped in `asyncio.to_thread()` to prevent event loop blocking
- **LRU cache** (100 entries) — repeated translations are instant
- **Graceful failure** — on error, returns original (English) text instead of crashing

---

## 5. Vertex AI Imagen (Visual Experience)

**Role**: AI-generated scene illustrations — pixel art for each scene

**Service**: `app/services/imagen_service.py`
**SDK**: `google-cloud-aiplatform` (Vertex AI)
**Model**: `imagen-3.0-generate-002`
**Toggle**: `ENABLE_IMAGEN=true`

### How It's Used
- Generates pixel-art illustrations based on scene descriptions
- Styled as "retro 80s aesthetic, neon glow effects, safe for children"
- Returns base64-encoded PNG displayed in the scene card

### Technical Details
```python
class ImagenService:
    def __init__(self):
        vertexai.init(project=settings.gcp_project_id, location="us-central1")
        self._model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")

    async def generate_scene_image(self, scene_description, style="pixel art"):
        prompt = f"A {style} illustration for a children's adventure game: {desc}. "
                 f"Retro 80s aesthetic, neon glow effects, safe for children, "
                 f"colorful, no text in image, no people."
        
        response = await asyncio.to_thread(
            self._model.generate_images,
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="16:9",
            safety_filter_level="block_most",
            person_generation="dont_allow",
        )
```

### Key Design Choices
- **Safety filters**: `safety_filter_level="block_most"` + `person_generation="dont_allow"` — child-safe output
- **Prompt engineering**: Scene description capped at 300 chars to prevent prompt injection
- **Thread offloading**: Sync SDK wrapped in `asyncio.to_thread()`
- **Aspect ratio**: 16:9 for cinematic scene cards

---

## 6. Cloud Storage (Asset CDN)

**Role**: Persistent storage for generated assets (audio, images)

**Service**: `app/services/storage_service.py`
**SDK**: `google-cloud-storage`
**Toggle**: `ENABLE_STORAGE=true`

### How It's Used
- Uploads TTS audio and Imagen illustrations to a GCS bucket
- Returns public URLs for frontend consumption
- Enables asset caching at the CDN layer

### Technical Details
```python
class StorageService:
    def __init__(self):
        self._client = storage.Client(project=settings.gcp_project_id)
        self._bucket = self._client.bucket(settings.gcs_bucket_name)

    async def upload_bytes(self, data, blob_name, content_type) -> str:
        blob = self._bucket.blob(blob_name)
        await asyncio.to_thread(blob.upload_from_string, data, content_type=content_type)
        await asyncio.to_thread(blob.make_public)
        return blob.public_url
```

---

## 7. Cloud Run (Serverless Compute)

**Role**: Production deployment with automatic scaling

### Configuration
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Memory | 512Mi | Sufficient for FastAPI + Gemini SDK |
| CPU | 1 vCPU | Single-worker uvicorn is CPU-bound on JSON parsing |
| Min instances | 0 | Scale to zero for cost efficiency |
| Max instances | 10 | Handles burst traffic |
| Concurrency | 80 | Async FastAPI handles many concurrent requests |
| Health check | `/api/health` | Returns version, uptime, feature flags |

### Integration Points
- **Cloud Trace**: Request logging middleware extracts `x-cloud-trace-context` header for distributed tracing
- **Cloud Logging**: Structured JSON logs (severity, module, function, line, trace ID) are captured natively from stdout
- **HTTPS**: Automatic TLS termination by Cloud Run

---

## 8. Cloud Build (CI/CD Pipeline)

**Role**: Automated build, test, and deploy pipeline

### Pipeline Steps
```yaml
steps:
  1. pytest          # Run full test suite
  2. docker build    # Multi-stage container (builder + runtime)
  3. docker push     # Push to Artifact Registry (commit SHA + latest)
  4. gcloud run deploy  # Deploy to Cloud Run with env vars
```

### Key Features
- **Test-first**: Pipeline fails fast if tests don't pass
- **Dual-tagged images**: Both `$COMMIT_SHA` and `latest` for traceability + convenience
- **Artifact Registry**: Container images stored in Google's managed registry
- **Environment injection**: All feature flags and API keys passed as Cloud Run env vars
- **Timeout**: 1200s (20 minutes) — generous for first-time builds

---

## Service Integration Pattern

All Google services follow the same integration pattern:

```python
# 1. Feature toggle in config.py
enable_tts: bool = _parse_bool(os.environ.get("ENABLE_TTS", "false"))

# 2. Lazy singleton in dependencies.py
def get_tts_service() -> TTSService | None:
    if not settings.enable_tts:
        return None           # Feature disabled
    if _tts_service is None:
        _tts_service = TTSService()  # First-request initialization
    return _tts_service

# 3. Route-level guard in routes/game.py
@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    tts = get_tts_service()
    if tts is None:
        raise HTTPException(status_code=503, detail="TTS not enabled")
    return TTSResponse(audio=await tts.synthesize(request.text))

# 4. Test override in conftest.py
app.dependency_overrides[get_tts_service] = lambda: mock_tts
```

This pattern ensures:
- **Zero initialization cost** for disabled services
- **Clear 503 responses** when features are unavailable
- **Complete testability** via dependency injection overrides
- **No import errors** — services are imported inside functions, not at module level
