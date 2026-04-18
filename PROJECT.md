# Scoutr — AI Product Finder

> Describe your problem. Get the perfect product.

Scoutr is an AI-powered product recommendation chatbot that takes a user's real-world problem and instantly recommends the best product to solve it — complete with affiliate purchase links.

---

## Tech Stack

| Layer        | Technology                    | Purpose                                  |
|-------------|-------------------------------|------------------------------------------|
| **Runtime** | Python 3.12                   | Stable release, full wheel support       |
| **Backend** | FastAPI + Uvicorn             | Async REST API with auto-reload          |
| **AI**      | OpenRouter API (OpenAI SDK)   | LLM inference via OpenAI-compatible endpoint |
| **Model**   | `google/gemma-4-31b-it:free`  | Free-tier Gemma model via OpenRouter     |
| **Frontend**| Single-file HTML/CSS/JS       | "Surgical Utility" dark theme design     |
| **Validation** | Pydantic v2               | Request/response schema enforcement      |
| **Rate Limiting** | SlowAPI               | Per-IP rate limiting (10 req/min)        |
| **Config**  | pydantic-settings + `.env`    | Environment-based secrets management     |

---

## Project Structure

```
Product Finder/
├── main.py                    # FastAPI app entry point, CORS, rate limiter, frontend serving
├── config.py                  # Pydantic Settings — loads .env variables
├── models.py                  # Pydantic models (ChatRequest, ChatResponse, ProductRecommendation)
├── index.html                 # Complete frontend (HTML + CSS + JS in one file)
├── .env                       # API keys & config (never commit this)
├── .env.example               # Template for .env
├── requirements.txt           # Python dependencies
├── Scoutr.md                    # Frontend design specification
├── routes/
│   ├── __init__.py
│   ├── chat.py                # POST /api/chat — main recommendation endpoint
│   └── health.py              # GET /health — uptime check
├── services/
│   ├── __init__.py
│   ├── ai_service.py          # OpenRouter API integration + retry logic
│   └── affiliate_service.py   # Amazon & Google Shopping link builder
└── venv/                      # Python virtual environment (gitignored)
```

---

## API Endpoints

| Method | Path         | Description                          |
|--------|-------------|--------------------------------------|
| GET    | `/`         | Serves the Scoutr frontend             |
| GET    | `/health`   | Server health check (for monitoring) |
| POST   | `/api/chat` | Send a problem, get a product rec    |

### POST `/api/chat` — Example

**Request:**
```json
{ "message": "My back hurts when I work from home" }
```

**Response:**
```json
{
  "intro": "I'm sorry to hear your back is acting up; the right support makes all the difference.",
  "product": {
    "name": "SIHOO M18 Ergonomic Office Chair",
    "category": "Office Furniture",
    "why": "Your back pain likely stems from poor lumbar support...",
    "search_query": "SIHOO M18 Ergonomic Office Chair",
    "links": {
      "amazon": "https://www.amazon.com/s?k=SIHOO+M18...&tag=your-tag-20",
      "google": "https://www.google.com/search?q=SIHOO+M18...&tbm=shop"
    },
    "also_consider": "Herman Miller Aeron"
  },
  "success": true
}
```

---

## Data Flow

```
User types problem
      │
      ▼
  index.html (frontend)
      │  POST /api/chat { "message": "..." }
      ▼
  routes/chat.py
      │  1. Validate input (Pydantic)
      │  2. Call AI service
      ▼
  services/ai_service.py
      │  → OpenRouter API (google/gemma-4-31b-it:free)
      │  ← JSON response parsed
      │  ↻ Retry up to 3x with backoff on failure
      ▼
  services/affiliate_service.py
      │  Build Amazon + Google Shopping links
      ▼
  routes/chat.py
      │  Assemble ChatResponse
      ▼
  Frontend renders product card
```

---

## Key Features

- **Retry Logic**: 3 attempts with exponential backoff (5s → 10s) for transient API failures
- **Rate Limiting**: 10 requests/IP/minute via SlowAPI (protects API costs)
- **Affiliate Links**: Auto-generated Amazon Associates links with your tag
- **Error Handling**: Graceful error bubbles in the UI instead of crashes
- **Design System**: Custom dark theme with CSS variables, animations (pulse, fadeUp, blink)

---

## Recent Updates

| Date       | Change                                                             |
|------------|---------------------------------------------------------------------|
| 2026-04-13 | Added retry logic with exponential backoff to `ai_service.py`       |
| 2026-04-13 | Switched API provider from xAI Grok → Google Gemini → **OpenRouter** |
| 2026-04-13 | Fixed SlowAPI rate limiter registration in `main.py`                |
| 2026-04-13 | Added `FileResponse` to serve frontend at `http://localhost:8000`   |
| 2026-04-13 | Removed unsupported `response_format` param for free-tier model     |
| 2026-04-12 | Built single-file frontend following Scoutr.md "Surgical Utility" spec|
| 2026-04-12 | Migrated from Anthropic Claude SDK to OpenAI SDK                    |
| 2026-04-12 | Set up Python 3.12 venv, installed all dependencies                 |

---

## How to Run

```bash
# 1. Activate the virtual environment
venv\Scripts\activate

# 2. Start the server
python main.py

# 3. Open in browser
# → http://localhost:8000
```

## Environment Variables (`.env`)

```
OPENROUTER_API_KEY=sk-or-v1-...    # Get from https://openrouter.ai/keys
OPENROUTER_MODEL=google/gemma-4-31b-it:free
OPENROUTER_MAX_TOKENS=1024
AMAZON_AFFILIATE_TAG=your-tag-20
ALLOWED_ORIGINS=["*"]
RATE_LIMIT_PER_MINUTE=10
```
