# QuestForge - AI-Powered Text Adventure

> A reimagination of classic text adventure games using Google Gemini AI, built for the PromptWars hackathon.

## Chosen Vertical

**Classic Game**: Text Adventure / Choose Your Own Adventure (Zork, CYOA books)

**Reimagined As**: An AI-powered infinite text adventure where Google Gemini acts as a dynamic dungeon master, generating unique stories, responding to free-form player input, and creating experiences that were impossible 20 years ago.

## How It Works

1. **Choose Your Adventure**: Pick a genre (Fantasy, Sci-Fi, Mystery, Horror, or Pirate) and enter your name.
2. **AI Storytelling**: Gemini generates an immersive opening scene with multiple choices.
3. **Play Your Way**: Select a suggested choice OR type any custom action - the AI adapts.
4. **Dynamic State**: Your health, inventory, and story evolve based on your decisions.
5. **Listen Along**: Click "Narrate" to hear the story read aloud via Google Cloud Text-to-Speech.
6. **Infinite Replayability**: Every playthrough is unique - no two stories are the same.

## Approach and Logic

### Architecture
```
Browser (Vanilla HTML/CSS/JS)
    │
    ▼ REST API + GZip
FastAPI (async, middleware stack)
    │
    ├── Google Gemini API ──── Story generation (structured JSON)
    ├── Cloud Firestore ────── Persistent game state
    ├── Cloud Text-to-Speech ─ Narrative narration
    └── Cloud Logging ──────── Structured JSON observability
    │
    ▼ Deployed via
Cloud Build → Cloud Run (serverless)
```

### AI Integration
- Gemini receives a carefully crafted system prompt acting as an expert storyteller
- Game state (health, inventory, history) is passed as context for narrative coherence
- Structured JSON output (`response_mime_type="application/json"`) ensures reliable parsing
- The AI dynamically adjusts difficulty and story complexity based on player actions

### Design Decisions
- **Vanilla JS frontend**: Zero framework overhead, well under 10MB limit
- **FastAPI + async**: Non-blocking I/O for Gemini, Firestore, and TTS calls
- **Dependency injection**: FastAPI `Depends()` for testable, swappable services
- **Graceful degradation**: Firestore and TTS are optional; app works with just Gemini
- **Structured Cloud Logging**: JSON-formatted stdout captured natively by Cloud Run

## Google Services Integration

| Service | Usage |
|---------|-------|
| **Gemini API** (gemini-2.0-flash) | Core AI engine - generates stories, processes player actions, manages game logic |
| **Cloud Firestore** | Persistent game state storage - games survive container restarts |
| **Cloud Text-to-Speech** | Narrates adventure text aloud as MP3 audio for immersion and accessibility |
| **Cloud Logging** | Structured JSON logs with severity, module, function, and trace correlation |
| **Cloud Run** | Serverless deployment with automatic scaling, HTTPS, and health checks |
| **Cloud Build** | CI/CD pipeline: build container, push to registry, deploy to Cloud Run |

## Security

- Non-root container user (`appuser`)
- Security headers: CSP, X-Frame-Options, X-Content-Type-Options, Permissions-Policy
- Rate limiting middleware (configurable per-minute threshold)
- Input validation with Pydantic field constraints (max lengths, required fields)
- No secrets in code - all credentials via environment variables
- CORS restricted to configured origins
- Swagger/ReDoc docs disabled in production

## Assumptions

- Players have a modern web browser with JavaScript enabled
- The Gemini API key is provided via environment variable (`GOOGLE_API_KEY`)
- Firestore and TTS are optional features enabled via environment variables
- The application is designed for single-player experiences
- Internet connectivity is required for AI-powered story generation

## Local Development

### Prerequisites
- Python 3.12+
- Google Cloud SDK with a valid Gemini API key

### Setup
```bash
pip install -r requirements.txt
export GOOGLE_API_KEY=your-key-here
python -m app.main
```

The app will be available at `http://localhost:8080`.

### Running Tests
```bash
pytest tests/ -v
```

## Deployment to Cloud Run

### Via Cloud Build (recommended)
```bash
gcloud builds submit --config=cloudbuild.yaml
```

### Via gcloud CLI
```bash
gcloud run deploy questforge \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_API_KEY=your-key,ENABLE_FIRESTORE=true,ENABLE_TTS=true
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | - | Gemini API key |
| `GCP_PROJECT_ID` | No | - | GCP project for Firestore |
| `ENABLE_FIRESTORE` | No | `false` | Enable persistent game storage |
| `ENABLE_TTS` | No | `false` | Enable text-to-speech narration |
| `PORT` | No | `8080` | Server port (set by Cloud Run) |
| `RATE_LIMIT_PER_MINUTE` | No | `60` | API rate limit per client IP |

## Project Structure

```
├── app/
│   ├── main.py                # FastAPI app with middleware stack
│   ├── config.py              # Environment-based configuration
│   ├── dependencies.py        # Lazy-initialized service singletons
│   ├── middleware.py           # Security headers, rate limiting, request logging
│   ├── logging_config.py      # Structured JSON logging for Cloud Logging
│   ├── models/
│   │   └── schemas.py         # Pydantic request/response models
│   ├── routes/
│   │   ├── game.py            # Game + TTS API endpoints
│   │   └── health.py          # Health check with feature flags
│   ├── services/
│   │   ├── gemini_service.py  # Gemini AI story generation
│   │   ├── game_engine.py     # Game state + Firestore persistence
│   │   ├── firestore_service.py # Cloud Firestore CRUD
│   │   └── tts_service.py     # Cloud Text-to-Speech synthesis
│   └── static/
│       ├── index.html         # Accessible game UI
│       ├── css/style.css      # Dark theme with genre variants
│       └── js/app.js          # Vanilla JS game controller
├── tests/                     # Comprehensive test suite
├── cloudbuild.yaml            # Cloud Build CI/CD pipeline
├── Dockerfile                 # Multi-stage, non-root container
├── requirements.txt           # Pinned Python dependencies
└── README.md
```

## Evaluation Criteria Addressed

- **Code Quality**: Modular architecture, dependency injection, type hints, docstrings, consistent patterns
- **Security**: Non-root container, CSP/security headers, rate limiting, input validation, no exposed secrets
- **Efficiency**: GZip compression, async I/O, lazy service init, multi-stage Docker, optimized static serving
- **Testing**: Comprehensive test suite covering models, routes, engine, middleware, and edge cases
- **Accessibility**: ARIA labels, keyboard navigation (number keys for choices), screen reader announcements, reduced motion, forced-colors support
- **Google Services**: Gemini AI, Cloud Firestore, Cloud TTS, Cloud Logging, Cloud Run, Cloud Build
