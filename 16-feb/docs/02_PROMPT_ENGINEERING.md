# Prompt Engineering & AI Logic Deep Dive

## The Core Thesis

QuestForge treats Google Gemini not as a chatbot, but as a **structured game engine**. Every AI response is constrained to return valid JSON conforming to a strict schema — making the AI deterministic enough for a game loop while retaining the creative freedom that makes each playthrough unique.

---

## System Prompt Architecture

The system prompt is 75 lines of carefully engineered instructions that transform Gemini into a child-safe dungeon master. Here's how each section works:

### 1. Role Definition
```
"You are the Dungeon Master for QuestForge: The Upside Down, an interactive
adventure game inspired by Stranger Things set in the 1980s."
```
- Sets the AI persona as a **Dungeon Master**, not an assistant
- Anchors the creative direction to a specific IP (Stranger Things) for tonal consistency
- Specifies the era (1980s) to guide vocabulary, setting, and item choices

### 2. Audience Guardrails
```
"The game is designed for young children (ages 4-8), so the tone must be
exciting but never truly scary -- spooky-fun, not terrifying."
```
- **Safety-first design**: The AI is explicitly told to never be frightening
- This is not just a content filter — it's a creative constraint that shapes the narrative
- "Think of the show's sense of wonder, friendship, and bravery rather than its horror elements"

### 3. Narrative Rules (10 constraints)
Each rule serves a specific game-design purpose:

| Rule | Purpose |
|------|---------|
| Write in second person ("You tiptoe...") | Immersion — player feels present |
| 1-2 paragraphs maximum | Pacing — keeps children engaged |
| Simple vocabulary | Accessibility — ages 4-8 audience |
| Exactly 3 distinct choices | Decision paralysis prevention |
| Choices under 10 words | Quick scannable options |
| Choices differ in approach (brave, careful, clever) | Meaningful player expression |
| Health changes must be narrative-justified | No arbitrary damage/healing |
| Never genuinely frightening | Child safety |
| Items must be narratively justified | Coherent world-building |
| Player is always the HERO | Empowerment, never helplessness |

### 4. Structured JSON Contract
The most critical engineering decision: **forcing the AI to respond in a strict JSON schema**.

```json
{
  "narrative": "Short, vivid story text...",
  "choices": ["Brave choice", "Careful choice", "Clever choice"],
  "choice_icons": ["sword", "shield", "magnifying-glass"],
  "health_delta": 0,
  "new_items": [],
  "removed_items": [],
  "is_complete": false,
  "scene_visual": {
    "scene_type": "exploration",
    "mood": "mysterious",
    "location_name": "Hawkins Forest",
    "location_icon": "forest",
    "npc_name": null,
    "npc_type": null,
    "item_found": null,
    "weather": "clear"
  },
  "map_update": {
    "new_location": "Hawkins Forest",
    "location_icon": "forest",
    "connects_to_previous": true
  }
}
```

**Why this matters:**
- `response_mime_type="application/json"` — Gemini's native JSON mode ensures valid output
- Every field drives a specific frontend rendering decision
- `scene_visual` powers the dynamic scene card (mood gradients, location icons, NPC encounters)
- `map_update` drives the procedural Canvas 2D exploration map
- `choice_icons` maps to a curated emoji vocabulary for visual choices

### 5. Enumerated Value Sets
The prompt defines closed vocabularies to prevent hallucinated values:

```
scene_type:    exploration | combat | discovery | puzzle | dialogue | escape
mood:          tense | cheerful | scary | mysterious | victorious | calm | exciting
location_icon: forest | lab | school | house | cave | town | library | arcade
               field | portal | bike-trail | basement
choice_icons:  sword | shield | magnifying-glass | flashlight | run | talk | key
               bike | walkie-talkie | book | potion | friend | sneak | climb
               door | puzzle | magic | hide
```

These enums are mirrored in the frontend's `Scene` module, ensuring a 1:1 mapping between AI output and visual rendering.

---

## Adventure Themes (Contextual Prompt Injection)

Each adventure type injects a different theme paragraph into the generation prompt:

### Hawkins Investigation
> "a mysterious investigation in the small town of Hawkins, Indiana in the 1980s. Strange things are happening: flickering lights, mysterious sounds, and odd signals on walkie-talkies."

### The Upside Down
> "a spooky-fun adventure through the Upside Down, a mirror world covered in vines and floating glowing particles. Everything glows with mysterious blue and red light."

### Hawkins Lab
> "an exciting escape from a mysterious laboratory full of blinking machines and long corridors. You have discovered you have special powers like telekinesis!"

### D&D Campaign
> "an epic Dungeons & Dragons campaign being played by friends in a cozy basement. Roll dice for exciting moments!"

Each theme:
- Establishes setting, tone, and mechanics
- References specific Stranger Things elements (walkie-talkies, the Upside Down, Eleven's powers, basement D&D)
- Ends with an explicit safety reminder

---

## Context Window Management

### History Compression
The system maintains narrative coherence by passing a **condensed history** to each generation call:

```python
def _build_history_context(game_state: dict) -> str:
    history = game_state.get("story_history", [])
    recent = history[-6:]  # Only last 6 turns
    parts = []
    for entry in recent:
        parts.append(f"- {entry.get('narrative', '')[:200]}")  # Truncated
        if entry.get("action"):
            parts.append(f"  Player chose: {entry['action']}")
    return "\n".join(parts)
```

**Design decisions:**
- **6-turn sliding window**: Balances context quality vs. token cost
- **200-char truncation per entry**: Prevents context explosion on long narratives
- **Action inclusion**: The AI sees what the player chose, enabling cause-and-effect storytelling

### Turn Prompt Construction
Each action prompt includes full game state context:

```
Continue the adventure for player {name}.

CURRENT STATE:
- Health: {health}/100
- Inventory: {items}
- Turn: {turn_count}

STORY SO FAR:
{compressed_history}

PLAYER ACTION: {action}

Narrate what happens next. Move to a NEW LOCATION. Keep it child-friendly!
```

This structure ensures:
- The AI knows current mechanical state (health, items)
- It has narrative context (recent story)
- It knows the player's intent (action)
- It's explicitly told to advance the map (new location)

---

## Safety Layers

### 1. Input Truncation (Prompt Injection Defense)
```python
safe_action = player_action[:500]
```
Player input is hard-truncated to 500 characters before injection into the prompt, preventing prompt-stuffing attacks.

### 2. Output Clamping (Health Delta)
```python
_MAX_HEALTH_DELTA = 20
health_delta = max(-_MAX_HEALTH_DELTA, min(_MAX_HEALTH_DELTA, raw_delta))
```
Even if Gemini returns `health_delta: -100`, the game engine clamps it to ±20. This prevents:
- One-hit kills that break game flow
- AI hallucinations causing instant death/full heal

### 3. Output Validation & Fallback
```python
def _parse_response(self, text: str) -> dict:
    try:
        data = json.loads(text)
        # Validate and clamp every field...
        return validated_data
    except (json.JSONDecodeError, ValueError, TypeError):
        return self._fallback_response()
```

If Gemini returns malformed JSON, the system falls back to a **safe, pre-written crossroads scene** — the game never crashes.

### 4. Choice and Item Limits
```python
"choices": choices[:4],           # Max 4 choices
"new_items": items[:5],           # Max 5 new items per turn
"removed_items": items[:5],       # Max 5 removed items per turn
```

### 5. Pydantic Boundary Validation
```python
class GameStartRequest(BaseModel):
    player_name: str = Field(..., min_length=1, max_length=50)
    adventure: Adventure  # Enum — only 4 valid values
    
    @field_validator("player_name")
    def _sanitise_player_name(cls, v):
        if not _SAFE_TEXT_RE.match(v):
            raise ValueError("Player name contains invalid characters")
        return v
```

Control characters and null bytes are rejected at the API boundary before reaching any business logic.

---

## Temperature & Model Configuration

```python
generation_config=genai.GenerationConfig(
    response_mime_type="application/json",
    temperature=0.9,
)
```

- **Model**: `gemini-3-flash-preview` — optimized for speed, ideal for real-time game interaction
- **Temperature**: `0.9` — high creativity for diverse storytelling, but constrained by the structured JSON contract
- **JSON mode**: `response_mime_type="application/json"` — guarantees parseable output
- The tension between high temperature and structured output is the **key insight**: it produces creative narratives within a mechanically reliable format

---

## What Makes This Prompt Engineering Exceptional

1. **Dual-purpose output**: A single API call returns both narrative text AND mechanical game data (health, items, map updates, scene metadata)
2. **Enumerated visual vocabulary**: The AI selects from predefined icon sets that map directly to frontend rendering
3. **Procedural map generation**: The AI generates a connected graph of locations, not just text
4. **Graceful degradation**: Fallback response ensures the game never breaks, even on API failure
5. **Child safety as a creative constraint**: The safety rules actually improve the narrative quality by forcing empowering, wonder-driven storytelling
6. **Context compression**: 6-turn sliding window with truncation keeps costs low without sacrificing coherence
