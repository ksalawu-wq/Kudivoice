"""
app.py — Top-level FastAPI application for KudiVoice AI.
Explicitly defines `app = FastAPI(...)` for Vercel serverless deployment
and serves the Impeccable frontend UI alongside the REST API.
"""

from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
import credit_scorer as cs
import database as db
from nvidia_extractor import extract_transaction
from schemas import ExtractedTransaction

# Initialize local SQLite DB tables
db.init_db()

# Vercel requires a literal top-level assignment: app = FastAPI(...)
app = FastAPI(
    title="KudiVoice AI",
    version="1.0.0",
    description="Voice-to-Ledger & Credit Profiler for African Merchants"
)

# Open CORS so frontend can call endpoints from any domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# Mount static CSS & JS assets
css_dir = FRONTEND_DIR / "css"
if css_dir.exists():
    app.mount("/css", StaticFiles(directory=str(css_dir)), name="css")

js_dir = FRONTEND_DIR / "js"
if js_dir.exists():
    app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")


class ExtractRequest(BaseModel):
    """Payload for /extract and /transaction."""
    text: str = Field(..., min_length=1, max_length=2000)


def _get_merchant_id(merchant_id: int | None) -> int:
    if merchant_id is not None:
        return merchant_id
    merchants = db.list_merchants()
    return merchants[0]["id"] if merchants else db.seed_demo_merchant()


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.post("/extract", response_model=ExtractedTransaction)
def extract(req: ExtractRequest) -> ExtractedTransaction:
    """Parse vernacular speech/text into a validated transaction."""
    return extract_transaction(req.text)


@app.post("/transaction")
def create_transaction(req: ExtractRequest, merchant_id: int | None = None) -> dict:
    """Extract and save transaction to SQLite ledger."""
    txn = extract_transaction(req.text)
    try:
        return db.add_transaction(_get_merchant_id(merchant_id), txn, source="text", raw_input=req.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@app.get("/transactions")
def list_transactions(merchant_id: int | None = None, limit: int | None = None) -> list[dict]:
    """Retrieve ledger transactions."""
    return db.get_transactions(_get_merchant_id(merchant_id), limit=limit)


@app.get("/debts")
def list_debts(merchant_id: int | None = None) -> list[dict]:
    """Retrieve outstanding customer debts."""
    return db.get_outstanding_debts(_get_merchant_id(merchant_id))


@app.get("/score")
def get_score(merchant_id: int | None = None) -> dict:
    """Compute KudiScore (300-850) and loan eligibility."""
    return cs.compute_kudiscore(_get_merchant_id(merchant_id))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "KudiVoice AI", "providers": config.secrets_status()}


# ---------------------------------------------------------------------------
# Frontend Root Route (Serves Impeccable HTML UI)
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_home():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return "<h1>KudiVoice AI</h1>"


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 KudiVoice AI server running at: http://localhost:{port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
