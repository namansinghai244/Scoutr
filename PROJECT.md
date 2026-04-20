# Scoutr

Scoutr is a FastAPI app with a single-file frontend that turns a user problem into four tiers of product recommendations: `cost_effective`, `basic`, `premium`, and `lavish`.

## Stack

- Backend: FastAPI + Uvicorn/Gunicorn
- AI: OpenRouter via the OpenAI Python SDK
- Validation: Pydantic v2
- Caching: `cachetools`
- Rate limiting: `slowapi`
- Frontend: single `index.html` file with inline CSS and JavaScript
- Images: DuckDuckGo image search via `ddgs` or `duckduckgo-search`

## Project Layout

```text
Product Finder/
├── main.py
├── config.py
├── models.py
├── index.html
├── .env.example
├── requirements.txt
├── render.yaml
├── Procfile
├── routes/
│   ├── chat.py
│   └── health.py
└── services/
    ├── affiliate_service.py
    ├── ai_service.py
    └── image_service.py
```

## API

### `GET /`

Serves the frontend from `index.html`.

### `GET /health`

Returns a lightweight uptime payload.

### `POST /api/chat`

Request:

```json
{
  "message": "My back hurts when I work from home",
  "history": []
}
```

Response shape:

```json
{
  "intro": "string",
  "cost_effective": [
    {
      "name": "string",
      "category": "string",
      "tagline": "string",
      "estimated_price": "string",
      "original_price": "string or null",
      "key_specs": ["string", "string", "string"],
      "why": "string",
      "search_query": "string",
      "asin": "string or null",
      "image_url": "string or null",
      "links": {
        "amazon": "string",
        "google": "string",
        "ebay": "string or null",
        "walmart": "string or null"
      }
    }
  ],
  "basic": [],
  "premium": [],
  "lavish": [],
  "success": true
}
```

Each tier must contain exactly three products.

## Runtime Notes

- `services/ai_service.py` retries malformed or incomplete model responses up to three times.
- `routes/chat.py` enriches AI results with affiliate links and bounded image fetches.
- `main.py` disables credentialed CORS automatically when `ALLOWED_ORIGINS` contains `"*"`.

## Environment Variables

```text
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct
OPENROUTER_MAX_TOKENS=3000
AMAZON_AFFILIATE_TAG=your-tag-20
EBAY_CAMPAIGN_ID=
WALMART_IMPACT_ID=
GENIUSLINK_TSID=
ALLOWED_ORIGINS=["*"]
RATE_LIMIT_PER_MINUTE=10
```

## Running Locally

```bash
pip install -r requirements.txt
python main.py
```

Then open `http://localhost:8000`.
