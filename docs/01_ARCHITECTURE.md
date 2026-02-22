# QuestForge: The Upside Down - System Architecture

## Executive Summary

QuestForge is a production-grade, AI-powered interactive text adventure game that reimagines classic Choose Your Own Adventure games using Google Gemini AI as a real-time dungeon master. The system is built on a modern async Python backend (FastAPI) with a zero-dependency vanilla JS frontend, deployed serverlessly on Google Cloud Run.

---

## High-Level Architecture

```
                          +---------------------------+
                          |      Browser Client       |
                          |   (Vanilla HTML/CSS/JS)   |
                          |                           |
                          |  +-----+  +-----+  +---+ |
                          |  | API |  |Sound|  |Map| |
                          |  |Client| |Mgr  |  |2D | |
                          |  +--+--+  +-----+  +---+ |
                          +-------|-------------------+
                                  | REST + GZip (HTTPS)
                          +-------|-------------------+
                          |  FastAPI Application      |
                          |                           |
                          |  +---------------------+  |
                          |  |  Middleware Stack    |  |
                          |  | CORS -> GZip ->     |  |
                          |  | RateLimit -> Log ->  |  |
                          |  | SecurityHeaders      |  |
                          |  +---------------------+  |
                          |           |                |
                          |  +--------v--------+      |
                          |  |   Route Layer    |      |
                          |  | /api/game/*      |      |
                          |  | /api/health      |      |
                          |  +--------+--------+      |
                          |           |                |
                          |  +--------v--------+      |
                          |  |  Game Engine     |      |
                          |  | (Orchestrator)   |      |
                          |  +--------+--------+      |
                          |           |                |
                          +-----------|----------------+
                                      |
                  +-------------------+-------------------+
                  |                   |                   |
        +---------v------+  +--------v-------+  +--------v-------+
        | Gemini Service |  | Firestore Svc  |  |  TTS Service   |
        | (AI Narrative) |  | (Persistence)  |  |  (Narration)   |
        +----------------+  +----------------+  +----------------+
                  |                   |                   |
        +---------v------+  +--------v-------+  +--------v-------+
        | Translate Svc  |  | Storage Svc    |  | Imagen Service |
        | (i18n)         |  | (GCS Assets)   |  | (Illustrations)|
        +----------------+  +----------------+  +----------------+
```

---

## Architectural Principles

### 1. Dependency Injection (FastAPI `Depends()`)
Every Google Cloud service is injected via FastAPI's dependency injection system. This provides:
- **Testability**: Services can be swapped with mocks using `app.dependency_overrides`
- **Lazy initialization**: Singletons are created on first request, not at import time
- **Feature toggling**: Services return `None` when disabled; routes respond with HTTP 503

### 2. Graceful Degradation
The system is designed to work with **only the Gemini API key**. Every other Google service is optional and toggleable:

```
Required:    Gemini API     (core narrative engine)
Optional:    Firestore      (persistent state)
             TTS            (audio narration)
             Translate      (multi-language)
             Cloud Storage  (asset CDN)
             Imagen         (scene illustrations)
```

When a service is unavailable, the application degrades gracefully:
- No Firestore -> in-memory game state (games lost on container restart)
- No TTS -> narrate button is handled client-side
- No Translate -> English only
- No Imagen -> CSS-rendered scene cards (mood gradients + icons)

### 3. Async-First Design
All I/O operations are non-blocking:
- Gemini SDK: native `generate_content_async()`
- Firestore: `AsyncClient` with native async `get()` / `set()`
- TTS: `TextToSpeechAsyncClient`
- Translate (v2 sync): wrapped in `asyncio.to_thread()`
- Imagen (sync): wrapped in `asyncio.to_thread()`
- Storage (sync): wrapped in `asyncio.to_thread()`

### 4. Security-by-Default
- Non-root container user (`appuser`)
- Comprehensive security headers (CSP, HSTS, X-Frame-Options, Permissions-Policy)
- Per-IP sliding-window rate limiting with bounded memory
- Input validation at API boundary (Pydantic constraints)
- No secrets in code; all via environment variables
- Swagger/ReDoc disabled in production

---

## Module Dependency Graph

```
app/
  main.py  ──────────>  config.py (Settings dataclass)
    |                      ^
    |                      | (imported by all modules)
    |
    +───> middleware.py    (SecurityHeaders, RateLimit, RequestLogging)
    |
    +───> routes/
    |       game.py  ───> dependencies.py  ───> services/*
    |       health.py ──> config.py
    |
    +───> static/         (served via StaticFiles mount)
            index.html
            css/style.css
            css/animations.css
            css/map.css
            js/app.js

services/
    gemini_service.py     Core AI (no dependencies except config)
    game_engine.py        Orchestrates Gemini + Firestore + state
    firestore_service.py  Async Firestore CRUD
    tts_service.py        Cloud TTS with LRU cache
    translate_service.py  Cloud Translate v2 with LRU cache
    storage_service.py    Cloud Storage upload/retrieve
    imagen_service.py     Vertex AI Imagen scene generation
```

---

## Request Flow (Complete Lifecycle)

### Game Start Flow
```
1. Client POST /api/game/start
      { player_name: "Max", adventure: "upside-down", language: "en" }

2. Middleware pipeline:
      CORS -> GZip -> RateLimit(check IP) -> RequestLogging(start timer)
      -> SecurityHeaders

3. Route: start_game()
      -> Pydantic validates GameStartRequest
      -> DI injects GameEngine singleton

4. GameEngine.create_game():
      a. Generate UUID for game_id
      b. Call GeminiService.generate_opening()
           -> Build themed prompt from ADVENTURE_THEMES
           -> Gemini API returns structured JSON
           -> Parse + validate + clamp health_delta
      c. Construct GameState (Pydantic model)
      d. Update procedural map (MapNode graph)
      e. Check achievement triggers
      f. Save to in-memory cache + Firestore (if enabled)
      g. Convert to GameResponse (public model)

5. Response:
      -> GZip compressed JSON
      -> Security headers attached
      -> Request logged with Cloud Trace ID and latency
```

### Action Processing Flow
```
1. Client POST /api/game/action
      { game_id: "uuid", action: "I search the mysterious lab" }

2. GameEngine.process_action():
      a. Load state (memory -> Firestore fallback)
      b. Validate game is alive and not complete
      c. Build context prompt with:
           - Current health, inventory, turn count
           - Last 6 story entries (condensed)
           - Player's action (truncated to 500 chars)
      d. GeminiService.generate_response() -> structured JSON
      e. Update:
           - Health (clamped 0-100)
           - Inventory (add/remove, deduped)
           - Story history
           - Scene visual metadata
           - Map nodes (bi-directional graph)
           - Achievements
           - XP
      f. Persist state
      g. Return GameResponse
```

---

## Data Models (Pydantic)

### Internal State
```python
GameState:
    game_id:        str          # UUID
    player_name:    str          # Validated, 1-50 chars
    adventure:      Adventure    # Enum (4 themes)
    health:         int          # 0-100, clamped
    inventory:      list[str]    # Order-preserving, no duplicates
    turn_count:     int          # >= 0
    narrative:      str          # Current scene text
    choices:        list[str]    # 3 choices max
    choice_icons:   list[str]    # Icon keys for each choice
    is_alive:       bool
    is_complete:    bool
    story_history:  list[dict]   # Turn log
    scene_visual:   SceneVisual  # Mood, location, NPCs, weather
    map_nodes:      list[MapNode]# Procedural exploration map
    current_node_id: str
    achievements:   list[str]
    xp:             int
    language:       str          # BCP-47 code
```

### API Boundary (Public Response)
```python
GameResponse:
    # Subset of GameState — excludes story_history, language
    game_id, narrative, choices, choice_icons, health,
    inventory, turn_count, is_alive, is_complete,
    scene_visual, map_nodes, current_node_id, achievements, xp
```

---

## Infrastructure

### Multi-Stage Dockerfile
```
Stage 1 (Builder):  python:3.12-slim
    -> pip install --prefix=/install (isolated dependency tree)

Stage 2 (Runtime):  python:3.12-slim
    -> Non-root user (appuser)
    -> COPY dependencies from builder
    -> COPY app/ only (no tests, no dev files)
    -> HEALTHCHECK via /api/health
    -> Single uvicorn worker (Cloud Run manages concurrency)
```

### Cloud Build Pipeline (CI/CD)
```
Step 1: Run pytest (full test suite)
Step 2: Build container with two tags (commit SHA + latest)
Step 3: Push to Artifact Registry
Step 4: Deploy to Cloud Run
         - 512Mi memory, 1 CPU
         - 0-10 instances (autoscale)
         - 80 concurrency per instance
         - All feature flags enabled via env vars
```

### Cloud Run Configuration
- **Memory**: 512Mi (sufficient for single-worker FastAPI + Gemini SDK)
- **CPU**: 1 vCPU
- **Scaling**: 0 min / 10 max instances (cost-efficient, scales to zero)
- **Concurrency**: 80 concurrent requests per instance
- **Health Check**: `/api/health` endpoint with uptime + feature flags
