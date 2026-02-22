# QuestForge — Staff Engineer Pitch Deck (Slide Notes)

## How To Use This Document
Each section below maps to a slide. The **Headline** is your slide title. The **Key Points** are your bullet points. The **Speaker Notes** are what you say out loud.

---

## SLIDE 1: Title

**Headline**: QuestForge: The Upside Down

**Subtitle**: Gemini as a Real-Time Game Engine — Not a Chatbot

**Tagline**: "What if the AI didn't answer your questions, but told you a story you've never heard before?"

---

## SLIDE 2: The Problem

**Headline**: The Limitation of Classic Text Adventures

**Key Points**:
- Text adventures (Zork, CYOA books) defined a generation — but had fixed, finite storylines
- Once you've read all paths, the game is over
- Player input was limited to pre-set choices
- No adaptation to player skill or creativity

**Speaker Notes**: "Every kid in the 80s played these. The magic was imagination — but the limitation was always the author's finite content. What if we removed that ceiling entirely?"

---

## SLIDE 3: The Architecture

**Headline**: 8 Google Services, 1 Coherent System

**Key Points**:
- Gemini API → AI narrative engine (core)
- Cloud Firestore → Persistent game state
- Cloud TTS → Audio narration (accessibility)
- Cloud Translate → 8 languages
- Vertex AI Imagen → Scene illustrations
- Cloud Storage → Asset CDN
- Cloud Run → Serverless compute (0 to 10 instances)
- Cloud Build → CI/CD pipeline (test → build → deploy)

**Speaker Notes**: "Every service is feature-toggled. The app works with just a Gemini API key. Turn on Firestore for persistence. Turn on TTS for accessibility. Each service adds a layer — none is required."

---

## SLIDE 4: The Prompt Architecture (The Heart)

**Headline**: Structured JSON Output — AI as a Game Engine

**Key Points**:
- 75-line system prompt transforms Gemini into a dungeon master
- `response_mime_type="application/json"` — every response is parseable game data
- Single API call returns: narrative text, 3 choices, health delta, inventory changes, scene metadata, map update
- Temperature 0.9 + JSON mode = creative but deterministic
- Fallback response on any failure — the game never crashes

**Speaker Notes**: "This is the key insight. We don't use Gemini as a text generator. We use it as a structured data generator that happens to produce narrative. Every field drives a rendering decision in the frontend."

---

## SLIDE 5: The JSON Contract

**Headline**: One API Call, Seven Rendering Decisions

**Visual**: Show the JSON response schema

```json
{
  "narrative":    "→ Typewriter text",
  "choices":      "→ Choice buttons",
  "health_delta": "→ Heart display update",
  "new_items":    "→ Inventory grid",
  "scene_visual": "→ Mood gradient + location icon",
  "map_update":   "→ Canvas 2D map node",
  "is_complete":  "→ Game over screen"
}
```

**Speaker Notes**: "A single Gemini call drives the entire UI update. The AI doesn't just write text — it makes game design decisions. It decides if the player found an item, took damage, moved to a new location, met an NPC. All structured, all validated, all clamped to safe ranges."

---

## SLIDE 6: Safety Engineering

**Headline**: Six Layers of Defense

**Key Points**:
1. Container: non-root user, multi-stage build
2. HTTP: CSP, HSTS, X-Frame-Options, Permissions-Policy
3. Rate limiting: per-IP sliding window, bounded memory (10K IPs max)
4. Input validation: Pydantic constraints, control char rejection
5. AI output clamping: health ±20 max, choices capped at 4, items at 5
6. Prompt injection defense: player input truncated to 500 chars

**Speaker Notes**: "The AI output is never trusted. Even if Gemini returns health_delta: -100, we clamp it to -20. The game engine treats Gemini as an untrusted data source — validate everything, trust nothing."

---

## SLIDE 7: The Service Integration Pattern

**Headline**: Feature Toggles + Lazy Singletons + DI = Production-Grade

**Visual**: Show the 4-step pattern

```
1. Config:       ENABLE_TTS=true          (env var)
2. Dependency:   get_tts_service() → TTSService | None
3. Route:        if service is None → 503
4. Test:         app.dependency_overrides[get_tts_service] = mock
```

**Speaker Notes**: "Every Google service follows the exact same pattern. Feature toggle in config. Lazy singleton in the dependency layer. Guard clause in the route. Test override in pytest. This is the kind of pattern that scales to 50 services without changing the architecture."

---

## SLIDE 8: Accessibility

**Headline**: Not an Afterthought — A Feature

**Key Points**:
- Screen reader: `aria-live` announcements on every turn
- Keyboard: number keys for choices, Enter for actions
- Audio: Cloud TTS reads the story aloud
- Language: Cloud Translate supports 8 languages
- Visual: skip-to-content, focus indicators, reduced motion, forced-colors
- Child-safe: AI prompt enforces empowering, never-scary narratives

**Speaker Notes**: "A child who can't read can play this game through voice alone. A child who doesn't speak English can play in Hindi. A child with motor disabilities can play with just number keys. This isn't compliance — it's inclusive design powered by Google's AI services."

---

## SLIDE 9: What a Staff Engineer Should Admire

**Headline**: Engineering Decisions That Scale

**Key Points**:
- **Async-first**: Every I/O operation is non-blocking — sync SDKs wrapped in `asyncio.to_thread()`
- **Bounded resources**: In-memory cache capped at 5K games, rate limiter at 10K IPs, TTS cache at 50 entries
- **Graceful degradation**: Remove any service — the app still works
- **Immutable config**: Frozen dataclass with validation — no runtime mutation
- **Zero-framework frontend**: 937 lines of vanilla JS, zero dependencies, under 50KB total
- **Context compression**: 6-turn sliding window keeps Gemini token costs O(1) per turn
- **Deterministic AI**: JSON mode + output clamping = creative but mechanically reliable

---

## SLIDE 10: The Numbers

**Headline**: By the Numbers

| Metric | Value |
|--------|-------|
| Backend Python LOC | ~1,200 |
| Frontend JS LOC | 937 |
| CSS LOC | ~1,500 |
| Test LOC | ~2,800 |
| Google services integrated | 8 |
| Pydantic models | 12 |
| API endpoints | 6 |
| Container image size | ~120MB |
| Cold start time | <2s |
| Memory footprint | 512Mi |
| Concurrent capacity | 80 req/instance |

---

## SLIDE 11: Future Vision

**Headline**: From Game to Platform

**Key Points**:
- Multiplayer via Firestore Realtime
- Voice-in via Cloud Speech-to-Text (full voice loop)
- Multimodal input via Gemini Vision (draw items into the game)
- Educational verticals (History, Science, Language Learning)
- Enterprise training (onboarding, compliance, sales scenarios)

**Speaker Notes**: "QuestForge isn't a game — it's a proof of concept for AI-native interactive experiences. The same architecture powers any use case where you need structured, coherent, multi-turn AI interaction with real-time state management."

---

## SLIDE 12: Close

**Headline**: "The best interface is a story."

**Speaker Notes**: "Twenty years ago, text adventures died because content was finite. Today, with Gemini, content is infinite. QuestForge proves that Google's AI services aren't just tools for answering questions — they're engines for creating experiences that have never existed before."
