# API Reference

## Base URL
```
Production: https://questforge-<hash>.run.app
Local:      http://localhost:8080
```

---

## Endpoints

### POST /api/game/start
Start a new game session.

**Request**:
```json
{
  "player_name": "Max",
  "adventure": "upside-down",
  "language": "en"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| player_name | string | yes | 1-50 chars, no control characters |
| adventure | enum | yes | `hawkins-investigation`, `upside-down`, `hawkins-lab`, `dnd-campaign` |
| language | string | no | 2-10 chars, BCP-47 code. Default: `en` |

**Response** (200): `GameResponse` (see below)

---

### POST /api/game/action
Process a player action.

**Request**:
```json
{
  "game_id": "uuid-string",
  "action": "I search the mysterious laboratory"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| game_id | string | yes | 1-128 chars |
| action | string | yes | 1-500 chars, no control characters |

**Response** (200): `GameResponse`
**Errors**: 404 (game not found), 400 (game already over), 500 (server error)

---

### GET /api/game/{game_id}
Retrieve current game state.

**Response** (200): `GameResponse`
**Errors**: 404 (game not found)

---

### POST /api/game/tts
Convert text to speech audio.

**Request**:
```json
{ "text": "You tiptoe through the dark corridor..." }
```

**Response** (200):
```json
{ "audio": "base64-encoded-mp3-string" }
```

**Errors**: 503 (TTS not enabled)

---

### POST /api/game/translate
Translate narrative text.

**Request**:
```json
{ "text": "You find a golden key.", "target_language": "es" }
```

**Response** (200):
```json
{ "translated_text": "Encuentras una llave dorada.", "source_language": "en" }
```

**Errors**: 503 (Translate not enabled)

---

### POST /api/game/image
Generate a scene illustration.

**Request**:
```json
{ "prompt": "A mysterious forest with glowing particles" }
```

**Response** (200):
```json
{ "image_url": "data:image/png;base64,..." }
```

**Errors**: 503 (Imagen not enabled)

---

### GET /api/health
Health check endpoint.

**Response** (200):
```json
{
  "status": "healthy",
  "service": "QuestForge: The Upside Down",
  "version": "2.0.0",
  "uptime_seconds": 3600,
  "features": {
    "gemini": true,
    "firestore": true,
    "tts": true,
    "translate": true,
    "storage": false,
    "imagen": false
  }
}
```

---

## GameResponse Schema

```json
{
  "game_id": "uuid",
  "narrative": "Story text...",
  "choices": ["Choice 1", "Choice 2", "Choice 3"],
  "choice_icons": ["sword", "shield", "magnifying-glass"],
  "health": 85,
  "inventory": ["flashlight", "walkie-talkie"],
  "turn_count": 3,
  "is_alive": true,
  "is_complete": false,
  "scene_visual": {
    "scene_type": "exploration",
    "mood": "mysterious",
    "location_name": "Hawkins Forest",
    "location_icon": "forest",
    "npc_name": null,
    "npc_type": null,
    "item_found": null,
    "weather": "foggy"
  },
  "map_nodes": [
    {
      "node_id": "node_0",
      "name": "Hawkins Forest",
      "visited": true,
      "connected_to": ["node_1"],
      "icon": "forest",
      "x": 0,
      "y": 0
    }
  ],
  "current_node_id": "node_0",
  "achievements": ["First Steps"],
  "xp": 35
}
```

---

## Error Responses

All errors follow this format:
```json
{ "detail": "Human-readable error message" }
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request (invalid input or game already over) |
| 404 | Game not found |
| 429 | Rate limit exceeded (Retry-After header included) |
| 500 | Internal server error |
| 503 | Service not enabled (TTS, Translate, Imagen, Storage) |
