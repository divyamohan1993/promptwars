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
5. **Infinite Replayability**: Every playthrough is unique - no two stories are the same.

## Approach and Logic

### Architecture
```
Frontend (Vanilla HTML/CSS/JS)
    │
    ▼ REST API
Backend (Python FastAPI)
    │
    ▼ Structured Prompts
Google Gemini API (gemini-2.0-flash)
    │
    ▼ Deployed on
Google Cloud Run
```

### AI Integration
- Gemini receives a carefully crafted system prompt that makes it act as an expert storyteller
- Game state (health, inventory, history) is passed as context for narrative coherence
- Structured JSON output ensures reliable parsing of narrative, choices, and state changes
- The AI dynamically adjusts difficulty and story complexity based on player actions

### Design Decisions
- **Vanilla JS frontend**: No framework overhead, stays well under 10MB limit
- **FastAPI backend**: Async-first, fast, with automatic OpenAPI documentation
- **In-memory game state**: Appropriate for a hackathon demo; easily swappable for Firestore
- **gemini-2.0-flash model**: Optimized for speed while maintaining narrative quality

## Google Services Integration

| Service | Usage |
|---------|-------|
| **Gemini API** | Core AI engine - generates stories, processes player actions, manages game logic |
| **Cloud Run** | Serverless deployment with automatic scaling and HTTPS |
| **Cloud Build** | Automated container builds from source |
| **Artifact Registry** | Container image storage and management |

## Assumptions

- Players have a modern web browser with JavaScript enabled
- The Gemini API key is provided via environment variable (`GOOGLE_API_KEY`)
- Game sessions are ephemeral (in-memory storage); persistent storage can be added with Firestore
- The application is designed for single-player experiences
- Internet connectivity is required for AI-powered story generation

## Local Development

### Prerequisites
- Python 3.12+
- Google Cloud SDK with a valid Gemini API key

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key
export GOOGLE_API_KEY=your-key-here

# Run the application
python -m app.main
```

The app will be available at `http://localhost:8080`.

### Running Tests
```bash
pytest tests/ -v
```

## Deployment to Cloud Run

```bash
# Build and deploy
gcloud run deploy questforge \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_API_KEY=your-key-here
```

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py             # Configuration management
│   ├── models/
│   │   └── schemas.py        # Pydantic data models
│   ├── routes/
│   │   ├── game.py           # Game API endpoints
│   │   └── health.py         # Health check endpoint
│   ├── services/
│   │   ├── gemini_service.py # Gemini AI integration
│   │   └── game_engine.py    # Game state management
│   └── static/
│       ├── index.html        # Game UI
│       ├── css/style.css     # Styling
│       └── js/app.js         # Frontend logic
├── tests/                    # Test suite
├── Dockerfile                # Container configuration
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Evaluation Criteria Addressed

- **Code Quality**: Modular architecture, type hints, clean separation of concerns
- **Security**: Non-root container, input validation, no secrets in code
- **Efficiency**: Async FastAPI, lightweight frontend, optimized container
- **Testing**: Comprehensive test suite with mocked AI service
- **Accessibility**: ARIA labels, keyboard navigation, screen reader support, reduced motion
- **Google Services**: Deep Gemini integration, Cloud Run deployment
