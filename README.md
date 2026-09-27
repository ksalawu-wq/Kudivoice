# KudiVoice AI

**Voice-to-Ledger & Credit Profiler for Nigerian informal traders.**

KudiVoice AI turns a trader's everyday spoken or typed words — in Pidgin or English — into a clean, validated bookkeeping ledger, then builds an explainable **KudiScore (300–850)** credit profile from that ledger alone. It ships as both a live Streamlit dashboard (`app.py`) and a stateless FastAPI REST backend (`api.py`) that a separate frontend can call.

---

## The problem it solves

Millions of Nigerian informal traders keep no formal books. Sales, credit given to customers ("carry am, I go pay later"), debt repayments, and restocking costs live in their heads. Because there is no financial record, these traders are effectively **invisible to lenders** — they cannot prove creditworthiness even when their business is healthy.

KudiVoice AI closes that gap:

1. **Effortless bookkeeping.** A trader says or types what happened in natural language ("Mama Chidi carry 3 bags of rice, 45k, she go pay later"). An LLM extractor parses it into a structured, schema-validated transaction and stores it in a kobo-safe ledger.
2. **A credit profile from behaviour, not demographics.** The KudiScore is computed from the trader's *own ledger activity* — consistency, cash flow, debt collection, sales stability, and record history. It maps onto the familiar 300–850 FICO-style range, with a risk grade (A/B/C) and a suggested max-loan ceiling in NGN.
3. **Debt follow-up.** Outstanding debts are surfaced with one-tap WhatsApp reminders.

### Responsible-AI by design
The score uses **only** transaction dates, amounts, types, and debt given/collected. It **never** uses name, gender, age, location, tribe/ethnicity, religion, language/dialect, or whether the entry was typed or spoken. A Pidgin or Hausa speaker is scored identically to an English speaker with the same ledger. Every score component reports its raw metric and the points it earned, so the result is fully auditable. New traders with too little data receive an `insufficient_data` status — never a punishing low score.

---

## Architecture

```
merchant utterance
        │
        ▼
 extract_transaction()      nvidia_extractor.py   (Gemini → Groq → offline demo fallback)
        │  ExtractedTransaction (schemas.py, Pydantic v2 — validates untrusted LLM output)
        ▼
 db.add_transaction()       database.py           (parameterised SQL, kobo-safe SQLite)
        │
        ▼
 compute_kudiscore()        credit_scorer.py      (deterministic, rule-based 300–850 + grade + loan)
```

| File | Role |
|------|------|
| `api.py` | FastAPI REST layer (deployment entrypoint: `api:app`) |
| `app.py` | Streamlit dashboard (same pipeline, interactive UI) |
| `nvidia_extractor.py` | LLM extraction with Gemini primary, Groq fallback, offline demo net |
| `schemas.py` | Pydantic v2 models — the defensive validation boundary for LLM output |
| `credit_scorer.py` | Explainable KudiScore, risk grade, max-loan recommendation |
| `database.py` | SQLite ledger, money/type parsers, debt aggregation |
| `config.py` | Single secrets choke-point (`.env` only, never hardcoded) |

---

## Setup

Requires **Python 3.11+**.

```bash
# 1. Clone
git clone https://github.com/ksalawu-wq/kudivoice.git
cd kudivoice

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure secrets (see below)
```

### Environment variables

Secrets are read **only** from a local `.env` file via `config.py` — never hardcoded. Copy the template and fill in your real keys:

```bash
# Windows PowerShell:
Copy-Item .env.example .env
# macOS / Linux:
cp .env.example .env
```

| Variable | Required | Purpose | Where to get it |
|----------|----------|---------|-----------------|
| `GEMINI_API_KEY` | Recommended | Google Gemini — the **primary** extraction model | https://aistudio.google.com/apikey |
| `GROQ_API_KEY` | Optional | Groq (Llama 3.3 70B) — automatic **fallback** if Gemini is unavailable | https://console.groq.com/keys (format `gsk_...`) |

Example `.env`:

```dotenv
GEMINI_API_KEY=your-gemini-key-here
GROQ_API_KEY=gsk_your-key-here
```

> **Offline demo net:** neither key is strictly required to boot. If no key or network is available, the extractor falls back to a valid demo transaction, so the app never crashes during a live demo. The keys are only needed to parse *arbitrary* real utterances. `.env` is git-ignored and must never be committed.

The root endpoint and Streamlit sidebar report only **booleans** about whether each provider is configured — the raw key values are never returned, printed, or logged.

---

## Running locally

### REST API (FastAPI)

```bash
uvicorn api:app --reload
```

Serves on `http://127.0.0.1:8000`. Interactive OpenAPI docs are auto-generated at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

### Dashboard (Streamlit)

```bash
streamlit run app.py
```

---

## Deployment

The repo includes a `Procfile` and `railway.toml` for a [Railway](https://railway.app) / Nixpacks deployment. Both start the API with:

```
uvicorn api:app --host 0.0.0.0 --port $PORT
```

Set `GEMINI_API_KEY` and `GROQ_API_KEY` as environment variables in your hosting provider's dashboard (do **not** commit `.env`).

> **⚠️ Security note:** the API ships with **wide-open CORS** (`allow_origins=["*"]`) and **no authentication** — this is intentional for a hackathon demo. Before any real deployment you must add authentication and lock CORS to your frontend's origin. Do not expose a real merchant's data this way.

---

## API reference

Base URL (local): `http://127.0.0.1:8000`

All request/response bodies are JSON. Endpoints that operate on a merchant accept an optional `?merchant_id=<int>` query parameter; if omitted, a seeded demo trader is used.

### `GET /` — health check

Returns service status and secret-safe provider configuration (booleans only).

**Request**
```bash
curl http://127.0.0.1:8000/
```

**Response** `200 OK`
```json
{
  "service": "KudiVoice AI API",
  "status": "ok",
  "providers": {
    "gemini": true,
    "groq": true
  }
}
```

---

### `POST /extract` — parse an utterance (does NOT save)

Parses a raw merchant utterance into a validated transaction and returns it **without persisting**. Always returns a schema-valid object (falls back to a demo transaction if the LLM providers are unreachable).

**Request**
```bash
curl -X POST http://127.0.0.1:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"text": "Mama Chidi carry 3 bags of rice, 45k, she go pay later"}'
```

| Field | Type | Notes |
|-------|------|-------|
| `text` | string | Required. 1–2000 chars. What the merchant said (Pidgin or English). |

**Response** `200 OK` — an `ExtractedTransaction`
```json
{
  "txn_type": "credit_sale",
  "amount": 45000.0,
  "item": "rice",
  "quantity": 3.0,
  "counterparty": "Mama Chidi",
  "note": null,
  "confidence": 0.94,
  "pidgin_confirmation": "I don record am: Mama Chidi carry rice for 45k credit."
}
```

`txn_type` is one of `sale`, `credit_sale`, `debt_payment`, `expense`.

---

### `POST /transaction` — extract AND save

Extracts from the utterance and persists it to the ledger, returning the saved row.

**Request**
```bash
curl -X POST "http://127.0.0.1:8000/transaction?merchant_id=1" \
  -H "Content-Type: application/json" \
  -d '{"text": "I sell 2 bottles of palm oil, 12,500, cash sharp sharp"}'
```

| Param | Location | Notes |
|-------|----------|-------|
| `text` | body | Required. 1–2000 chars. |
| `merchant_id` | query | Optional. Defaults to the seeded demo trader. |

**Response** `200 OK` — the saved ledger row
```json
{
  "id": 7,
  "merchant_id": 1,
  "txn_type": "sale",
  "amount_naira": 12500.0,
  "item": "palm oil",
  "quantity": 2.0,
  "counterparty": null,
  "note": null,
  "source": "text",
  "occurred_at": "2026-09-27T14:05:32"
}
```

**Error** `422 Unprocessable Entity` — the validation guard rejected the record (e.g. a `credit_sale`/`debt_payment` with no counterparty name):
```json
{ "detail": "credit_sale and debt_payment require a counterparty name" }
```

---

### `GET /transactions` — list ledger rows

Returns all ledger rows for the merchant, newest first.

**Request**
```bash
curl "http://127.0.0.1:8000/transactions?merchant_id=1&limit=5"
```

| Param | Notes |
|-------|-------|
| `merchant_id` | Optional. Defaults to the demo trader. |
| `limit` | Optional. Cap the number of rows returned. |

**Response** `200 OK`
```json
[
  {
    "id": 7,
    "merchant_id": 1,
    "txn_type": "sale",
    "amount_naira": 12500.0,
    "item": "palm oil",
    "quantity": 2.0,
    "counterparty": null,
    "note": null,
    "source": "text",
    "occurred_at": "2026-09-27T14:05:32"
  },
  {
    "id": 6,
    "merchant_id": 1,
    "txn_type": "credit_sale",
    "amount_naira": 45000.0,
    "item": "rice",
    "quantity": 3.0,
    "counterparty": "Mama Chidi",
    "note": null,
    "source": "text",
    "occurred_at": "2026-09-27T14:03:10"
  }
]
```

---

### `GET /debts` — outstanding debts

Returns outstanding debts (derived by aggregation), biggest first.

**Request**
```bash
curl "http://127.0.0.1:8000/debts?merchant_id=1"
```

**Response** `200 OK`
```json
[
  {
    "counterparty": "Mama Chidi",
    "owed_naira": 45000.0,
    "days_since_activity": 9
  },
  {
    "counterparty": "Oga Emeka",
    "owed_naira": 3000.0,
    "days_since_activity": 2
  }
]
```

---

### `GET /score` — KudiScore, grade, and max loan

Returns the current explainable KudiScore (300–850), risk grade (A/B/C), suggested max-loan ceiling in NGN, the full component breakdown, recommendations, and a fairness declaration.

**Request**
```bash
curl "http://127.0.0.1:8000/score?merchant_id=1"
```

**Response** `200 OK` — sufficient data
```json
{
  "merchant_id": 1,
  "window_days": 30,
  "period": { "from": "2026-08-28", "to": "2026-09-27" },
  "generated_at": "2026-09-27T14:06:00",
  "status": "ok",
  "kudiscore": 712,
  "score_100": 75,
  "risk_grade": "A",
  "band": "Strong",
  "band_message": "Ready to approach lenders",
  "max_loan_ngn": 185000,
  "explanation": "KudiScore 712/850 — Grade A (Strong). Suggested loan ceiling ₦185,000, sized to about ₦231,000 monthly cash flow and your debt-collection record.",
  "components": [
    {
      "key": "consistency",
      "label": "Trading consistency",
      "points": 20.8,
      "max_points": 25,
      "status": "good",
      "metric": "Active on 18 of the last 30 days"
    }
  ],
  "recommendations": [
    {
      "component": "cash_flow",
      "label": "Cash flow health",
      "potential_gain": 6.2,
      "tip_en": "Your margin is 18%. Spending is close to what comes in. Check your restock costs and selling prices.",
      "tip_pcm": "Wetin you dey spend don near wetin you dey gain. Check how you dey buy stock and how you dey price your goods."
    }
  ],
  "debtors": [
    { "counterparty": "Mama Chidi", "owed_naira": 45000.0, "days_since_activity": 9 }
  ],
  "summary": {
    "cash_in": 231000.0,
    "monthly_cash_in": 231000.0,
    "expenses": 90000.0,
    "net_cash": 141000.0,
    "outstanding_debt": 48000.0,
    "transactions": 14,
    "active_days": 8
  },
  "fairness": {
    "inputs_used": ["transaction dates", "transaction amounts", "transaction types", "debt given and collected"],
    "never_used": ["name", "gender", "age", "location", "tribe or ethnicity", "religion", "language or dialect", "voice vs text input"]
  }
}
```

**Response** `200 OK` — insufficient data (new trader). Note: this is **not** an error and **not** a low score.
```json
{
  "merchant_id": 2,
  "window_days": 30,
  "status": "insufficient_data",
  "kudiscore": null,
  "risk_grade": null,
  "band": "Not enough records yet",
  "band_message": "Record at least 10 transactions over 5 different days to unlock your KudiScore. You have 2 across 1 day(s).",
  "max_loan_ngn": 0,
  "components": [],
  "recommendations": [],
  "debtors": []
}
```

---

## Security & privacy summary

- **Secrets** live only in `.env`, loaded through the single choke-point in `config.py`. The API and UI expose booleans about provider configuration, never key values.
- **Untrusted LLM output** is validated and coerced against the Pydantic schema in `schemas.py` before it can reach SQL or the UI.
- **SQL** is fully parameterised in `database.py`.
- **Data minimisation:** phone numbers are never stored in the schema; raw utterances are stored only if `KUDIVOICE_STORE_RAW=true` (off by default).
- **Known gap (by design for the demo):** the REST API has no authentication and open CORS — add both before any real deployment.

