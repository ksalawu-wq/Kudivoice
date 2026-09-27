"""
api.py — FastAPI REST layer for the KudiVoice backend.

Exposes the same pipeline the Streamlit app uses (extract -> validate -> store
-> score) over HTTP, so a separate frontend (e.g. a Vercel deployment) can call
it:

    POST /extract       {text}          -> ExtractedTransaction (parsed, NOT saved)
    POST /transaction   {text}          -> extract + save, returns the saved row
    GET  /transactions                  -> ledger rows (newest first)
    GET  /debts                         -> outstanding debts (derived)
    GET  /score                         -> KudiScore, grade A/B/C, max loan NGN
    GET  /                              -> health + secret-safe provider status

Run locally:   uvicorn api:app --reload
Run for demo:  uvicorn api:app --host 0.0.0.0 --port 8000

SECURITY NOTES
  * CORS is intentionally wide open (allow_origins=["*"]) so the hosted frontend
    can call it from any origin, as requested. Because "*" origins and
    credentialed requests are mutually exclusive per the CORS spec, we set
    allow_credentials=False — this API carries no cookies/sessions.
  * ⚠️ There is NO authentication on these endpoints (auth is explicitly out of
    scope for this project). Combined with open CORS, that means ANYONE who can
    reach the URL can write transactions and read the ledger. This is fine for a
    hackathon demo, but before any real deployment you MUST add auth and lock
    CORS to your frontend's origin. Do not expose a real merchant's data this way.
  * Secrets stay in .env via config.py; the root endpoint returns booleans only,
    never key values. LLM input is sanitised and output schema-validated exactly
    as in the Streamlit path (the extractor and DB layer are unchanged).
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
import credit_scorer as cs
import database as db
from nvidia_extractor import extract_transaction
from schemas import ExtractedTransaction

# Ensure the schema exists before any request is served.
db.init_db()

app = FastAPI(
    title="KudiVoice AI API",
    version="1.0.0",
    description="Voice-to-Ledger & Credit Profiler for Nigerian informal traders.",
)

# Open CORS so the hosted frontend can call from any origin (see module docstring).
# allow_credentials MUST be False when allow_origins is "*" (CORS spec); this API
# is stateless and carries no cookies, so that is correct here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExtractRequest(BaseModel):
    """Body for /extract and /transaction — one raw merchant utterance."""
    text: str = Field(..., min_length=1, max_length=2000,
                      description="What the merchant said (Pidgin or English).")


@lru_cache(maxsize=1)
def _default_merchant_id() -> int:
    """The merchant used when no ?merchant_id= is supplied. Seeds the demo trader
    on first use so a fresh deployment has something to score (DEMO RESILIENCE)."""
    merchants = db.list_merchants()
    return merchants[0]["id"] if merchants else db.seed_demo_merchant()


def _merchant_id(merchant_id: int | None) -> int:
    return merchant_id if merchant_id is not None else _default_merchant_id()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def root() -> dict:
    """Health check + secret-safe provider status (booleans only, never keys)."""
    return {"service": "KudiVoice AI API", "status": "ok",
            "providers": config.secrets_status()}


@app.post("/extract", response_model=ExtractedTransaction)
def extract(req: ExtractRequest) -> ExtractedTransaction:
    """Parse an utterance into a validated transaction. Does NOT persist it.
    Always returns a schema-valid object (extractor falls back to a demo txn)."""
    return extract_transaction(req.text)


@app.post("/transaction")
def create_transaction(req: ExtractRequest, merchant_id: int | None = None) -> dict:
    """Extract from the utterance AND save it to the ledger. Returns the saved row."""
    txn = extract_transaction(req.text)
    try:
        # raw_input is stored only if KUDIVOICE_STORE_RAW=true (data minimisation).
        return db.add_transaction(_merchant_id(merchant_id), txn,
                                  source="text", raw_input=req.text)
    except ValueError as exc:  # validation guard rejected the record
        raise HTTPException(status_code=422, detail=str(exc)) from None


@app.get("/transactions")
def list_transactions(merchant_id: int | None = None,
                      limit: int | None = None) -> list[dict]:
    """All ledger rows for the merchant, newest first (optional ?limit=)."""
    return db.get_transactions(_merchant_id(merchant_id), limit=limit)


@app.get("/debts")
def list_debts(merchant_id: int | None = None) -> list[dict]:
    """Outstanding debts (derived by aggregation), biggest first."""
    return db.get_outstanding_debts(_merchant_id(merchant_id))


@app.get("/score")
def get_score(merchant_id: int | None = None) -> dict:
    """Current KudiScore (300–850), risk grade A/B/C, max-loan NGN, and the full
    explainable breakdown. Returns status='insufficient_data' for new traders."""
    return cs.compute_kudiscore(_merchant_id(merchant_id))
