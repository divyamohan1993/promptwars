# Core Functionality & Game Engine

## The Game Loop

QuestForge implements a classic game loop pattern adapted for AI-driven narrative:

```
                    +-----------+
                    |   START   |
                    +-----+-----+
                          |
                          v
                +-------------------+
                | Player chooses    |
                | adventure + name  |
                +--------+----------+
                         |
                         v
              +---------------------+
              | Gemini generates    |
              | opening narrative   |
              | + initial state     |
              +--------+------------+
                       |
                       v
             +--------------------+
         +-->| Render scene       |
         |   | Update UI          |
         |   | Present choices    |
         |   +--------+-----------+
         |            |
         |            v
         |   +--------------------+
         |   | Player action      |
         |   | (choice OR         |
         |   |  free-form text)   |
         |   +--------+-----------+
         |            |
         |            v
         |   +--------------------+
         |   | Gemini generates   |
         |   | next narrative     |
         |   +--------+-----------+
         |            |
         |            v
         |   +--------------------+
         |   | Update game state  |
         |   | Health, Inventory  |
         |   | Map, Achievements  |
         |   +--------+-----------+
         |            |
         |            v
         |   +--------------------+
         |   | Game over?         |--YES--> Game Over Screen
         |   +--------+-----------+
         |            | NO
         +------------+
```

---

## Game Engine (Orchestrator)

The `GameEngine` class (`app/services/game_engine.py`, 284 lines) is the central controller. It orchestrates:

### State Management
```python
class GameEngine:
    def __init__(self, gemini_service, firestore_service=None):
        self._games: dict[str, GameState] = {}     # In-memory cache
        self._gemini = gemini_service               # AI narrative
        self._firestore = firestore_service          # Optional persistence
```

### Create Game Flow
1. Generate UUID game ID
2. Resolve adventure theme from enum
3. Call `GeminiService.generate_opening()` with theme + player name
4. Construct `GameState` Pydantic model
5. Build initial map node
6. Check for "First Steps" achievement
7. Award initial XP (10 per turn)
8. Save state (memory + optional Firestore)
9. Return `GameResponse` (public-facing subset)

### Process Action Flow
1. Load state (memory -> Firestore fallback)
2. Validate: game must be alive and not complete
3. Call `GeminiService.generate_response()` with full context
4. Update health (clamped 0-100)
5. Update inventory (order-preserving, no duplicates)
6. Append to story history
7. Update scene visual metadata
8. Extend procedural map (bi-directional graph)
9. Check achievement triggers
10. Persist updated state
11. Return `GameResponse`

---

## Inventory System

The inventory uses a simple but effective design:

```python
# Add items — order-preserving, no duplicates
for item in ai_response.get("new_items", []):
    if item not in inventory:
        inventory.append(item)

# Remove items — by value
for item in ai_response.get("removed_items", []):
    if item in inventory:
        inventory.remove(item)
```

- Items are plain strings (e.g., "rusty sword", "walkie-talkie")
- The frontend maps item names to emojis via fuzzy keyword matching:
  ```javascript
  getItemIcon(itemName) {
      const lower = itemName.toLowerCase();
      for (const [key, icon] of Object.entries(this.ITEM_ICONS)) {
          if (lower.includes(key)) return icon;
      }
      return "📦";  // Default box icon
  }
  ```
- 18 item icons mapped (flashlight, walkie-talkie, bike, key, sword, shield, map, potion, book, torch, compass, rope, gem, coin, ring, wand, helmet, scroll)

---

## Procedural Map Generation

The game generates an exploration map as a bi-directional graph:

```python
class MapNode(BaseModel):
    node_id: str                    # "node_0", "node_1", ...
    name: str                       # "Hawkins Forest" (max 40 chars)
    visited: bool = False
    connected_to: list[str] = []    # Bi-directional edges
    icon: str = "location"          # Location type for rendering
    x: int = 0                      # Grid position
    y: int = 0
```

### How Map Updates Work
1. Gemini returns `map_update.new_location` in its JSON response
2. `GameEngine._update_map()` creates a new `MapNode`
3. Bi-directional edge is created between current and new node
4. Player's `current_node_id` advances to the new node
5. Grid position is auto-calculated: `x = len(nodes) % 5`, `y = len(nodes) // 5`

### Frontend Map Rendering (Canvas 2D)
```javascript
const MapRender = {
    render(nodes, currentId) {
        // 1. Clear canvas with dark background
        // 2. Calculate positions with padding
        // 3. Draw connection lines (#333346)
        // 4. Draw nodes:
        //    - Current node: red glow (#cc2200), larger radius
        //    - Visited nodes: cyan (#00d4ff)
        //    - Unvisited: gray (#333346)
        // 5. Draw location icons (emoji) above nodes
        // 6. Draw truncated labels below nodes
    }
};
```

---

## Achievement System

Six achievements with XP rewards:

| Achievement | Trigger | XP |
|-------------|---------|-----|
| First Steps | Turn 1 completed | 25 |
| Explorer | 5+ locations on map | 25 |
| Collector | 3+ items in inventory | 25 |
| Survivor | 10+ turns played | 25 |
| Brave Heart | Health ≤ 30 while still alive | 25 |
| Full Health | Health = 100 after turn 1 | 25 |

### XP System
- **10 XP per turn** (base)
- **25 XP per achievement** (bonus)
- XP is cumulative and displayed in the stats bar

### Achievement Detection
```python
@staticmethod
def _check_achievements(state: GameState) -> list[str]:
    new_achievements = []
    triggers = {
        "First Steps": state.turn_count == 1,
        "Explorer": len(state.map_nodes) >= 5,
        "Collector": len(state.inventory) >= 3,
        "Survivor": state.turn_count >= 10,
        "Brave Heart": state.health <= 30 and state.is_alive,
        "Full Health": state.health == 100 and state.turn_count > 1,
    }
    for name, condition in triggers.items():
        if condition and name not in state.achievements:
            state.achievements.append(name)
            new_achievements.append(name)
    return new_achievements
```

---

## Health System

- **Range**: 0-100 (clamped by `max(0, min(100, value))`)
- **AI-driven**: Gemini decides health changes based on narrative
- **Double-clamped**: AI output clamped to ±20 per turn, then result clamped to 0-100
- **Visual**: 5-heart display with full/half/empty states
- **Color-coded number**: Green (>60), Yellow (30-60), Red (<30)
- **Death**: health = 0 triggers game over
- **Completion**: `is_complete = true` after 8+ turns for natural endings

### Frontend Heart Rendering
```javascript
updateHearts(health) {
    const pct = health / this.maxHealth;
    hearts.forEach((heart, i) => {
        const threshold = (i + 1) / hearts.length;
        if (pct >= threshold) {
            heart.textContent = "❤️";      // Full
        } else if (pct >= threshold - offset) {
            heart.textContent = "❤️";      // Half (styled)
        } else {
            heart.textContent = "🖤";      // Empty
        }
    });
}
```

---

## Frontend Architecture (Vanilla JS)

The frontend is organized into 6 modules in a single `app.js` file (937 lines):

### Module 1: API Client
- Fetch wrapper for all 6 API endpoints
- Error handling with JSON error detail extraction
- Promise-based async/await

### Module 2: Sound Manager (Web Audio API)
- Synthesized sound effects — no audio files needed
- 7 sound types: click, item pickup, damage, heal, achievement, victory, defeat
- Uses `OscillatorNode` with different waveforms (sine, square, sawtooth)
- Lazy initialization on first user interaction (browser autoplay policy)
- Toggle on/off via header button

### Module 3: Map Renderer (Canvas 2D)
- Procedural map rendering on `<canvas>`
- Node-edge graph visualization
- Glowing current location, colored visited/unvisited nodes
- Emoji location icons
- Responsive positioning with padding calculations

### Module 4: Scene Renderer
- Maps AI-returned metadata to visual elements
- 8 mood types with corresponding icons and CSS gradients
- 12 location icons, 18 choice icons, 18 item icons, 6 achievement icons
- NPC encounter overlay for character appearances

### Module 5: Accessibility (A11y)
- Screen reader announcements via `aria-live="assertive"` region
- `requestAnimationFrame` used to ensure SR reads new content
- Keyboard shortcuts (1-9 for choices, Enter for actions)
- Skip-to-content link, ARIA labels on all interactive elements

### Module 6: Game Controller
- Main state machine (start -> game -> gameover screens)
- DOM caching for performance (40+ elements cached on init)
- Typewriter animation with skip-on-click
- Event binding for all interactive elements
- Theme application per adventure type

---

## Typewriter Effect

The narrative is revealed character-by-character for dramatic effect:

```javascript
async typewrite(text) {
    return new Promise((resolve) => {
        let i = 0;
        const cursor = document.createElement("span");
        cursor.className = "typewriter-cursor";
        entry.appendChild(cursor);

        this.typewriterTimer = setInterval(() => {
            if (i < text.length) {
                cursor.before(document.createTextNode(text[i]));
                i++;
                this.els.narrative.scrollTop = this.els.narrative.scrollHeight;
            } else {
                clearInterval(this.typewriterTimer);
                cursor.remove();
                resolve();
            }
        }, 18);  // 18ms per character = ~55 chars/second
    });
}
```

- **Speed**: 18ms per character (~55 chars/second)
- **Skippable**: Click on narrative area to instantly reveal full text
- **Auto-scroll**: Scrolls to bottom as text appears
- **Cursor animation**: Blinking cursor during typing (CSS animation)
- **Promise-based**: Choices are rendered only after typewriter completes

---

## Accessibility Features

QuestForge implements WCAG 2.1 AA level accessibility:

| Feature | Implementation |
|---------|---------------|
| Skip to content | `<a href="#main-content" class="skip-link">` |
| Screen reader announcements | `aria-live="assertive"` region updated per turn |
| Keyboard navigation | Number keys (1-9) select choices, Enter submits actions |
| ARIA labels | All buttons, inputs, regions, and interactive elements labeled |
| Reduced motion | `@media (prefers-reduced-motion)` disables animations |
| Forced colors | `@media (forced-colors: active)` support |
| Focus indicators | Custom `:focus-visible` outlines with accent color |
| Semantic HTML | `<main>`, `<header>`, `<footer>`, `<section>`, `<nav>` |
| Color-blind safe | Health uses text + hearts, not color alone |
| Form hints | `aria-describedby` linking inputs to help text |
