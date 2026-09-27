"""
nvidia_extractor.py — LLM extraction layer for KudiVoice AI.

(Filename kept to match the project's required deliverable list; the primary
provider is now Google Gemini, not NVIDIA NIM.)

Turns a raw merchant utterance (Nigerian Pidgin/English, typed or transcribed)
into a validated `ExtractedTransaction`. Provider order:

    1. Google Gemini  (see config.GEMINI_MODEL)       — primary
    2. Groq           (see config.GROQ_MODEL)          — automatic fallback
    3. Hardcoded, schema-valid transaction            — offline demo safety net

Both providers expose an OpenAI-compatible /chat/completions API (Gemini via
its `/v1beta/openai/` compatibility layer), so the same messages +
response_format payload is reused for each — see `_call_llm`.

SECURITY / PRIVACY DESIGN
-------------------------
* INPUT SANITISATION (see `_sanitize_input`): the raw string is treated as
  untrusted. We strip control characters, hard-cap the length, and collapse
  whitespace before it ever reaches the model. This bounds payload size and
  keeps hostile bytes out of both the API call and our logs. We also wrap the
  user text in an explicit delimiter so the model treats it as DATA, not
  instructions (defence-in-depth against prompt injection — the real guarantee
  is that the OUTPUT is schema-validated, never trusted).
* OUTPUT IS UNTRUSTED: model output is parsed and validated against
  `ExtractedTransaction` (schemas.py). Anything that does not validate is
  discarded and we fall through to the next provider / the safe default.
* NO PII IN LOGS: we log only provider name + exception *type*, never the
  merchant's utterance, customer name, phone, or the model's response body.
"""

from __future__ import annotations

import json
import logging
import re

import requests

import config
from schemas import ExtractedTransaction

# Module logger. IMPORTANT: never pass merchant utterances, names, or phone
# numbers to this logger — only provider/status metadata (no PII).
logger = logging.getLogger("kudivoice.extractor")

# Hard cap on accepted input length. A single spoken transaction is short;
# anything larger is almost certainly noise or abuse, so we clip it.
_MAX_INPUT_CHARS = 2000

# ---------------------------------------------------------------------------
# System prompt — includes the Nigerian Pidgin glossary the model must apply.
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """You are KudiVoice, a ledger assistant for Nigerian informal \
merchants. You convert ONE spoken/typed transaction into STRICT JSON.

NIGERIAN PIDGIN GLOSSARY (apply literally):
- "carry go" / "carry am go" / "collect now pay later" => a CREDIT sale (goods
  taken now, paid later) => txn_type "credit_sale"
- "balance me" / "don balance me" / "come pay" => the customer is REPAYING a
  debt => txn_type "debt_payment"
- "cash" / "sharp sharp" / "pay complete" => paid in full now => txn_type "sale"
- buying from a supplier / "I buy" / "restock" / "market" => txn_type "expense"
- "k" means thousands of Naira: "45k" = 45000, "20k" = 20000. "m" means millions.
- Units are things like "bags", "cartons", "pcs", "crates". Treat
  "3 bags of rice" as quantity=3, item="rice".
- Currency is ALWAYS Nigerian Naira (NGN). Never output another currency.

FIELD RULES:
- txn_type: EXACTLY one of "sale", "credit_sale", "debt_payment", "expense".
- amount: a single NGN number for THIS transaction:
    * sale         -> cash received now
    * credit_sale  -> value of the goods taken on credit
    * debt_payment -> the amount repaid
    * expense      -> the amount spent
- item: the main good (e.g. "rice"), or null if none is named.
- quantity: number of units (e.g. 3), or null if not stated.
- counterparty: the customer or supplier named. REQUIRED for "credit_sale" and
  "debt_payment". Use null if genuinely none is stated for a sale/expense.
- note: a short free-text detail, or null.
- confidence: your confidence from 0 to 1 that you read the transaction right.
- pidgin_confirmation: a short friendly Pidgin sentence confirming the record,
  e.g. "I don record am. Mama Chidi carry 3 bags of rice, 45k, she go pay later."

OUTPUT RULES:
- Respond with a SINGLE JSON object and NOTHING else. No markdown, no prose.
- Every monetary value is a plain number in NGN (45000, not "45k", not a symbol).
"""

def _is_control(ch: str) -> bool:
    code = ord(ch)
    return code < 0x20 or code == 0x7F


def _sanitize_input(raw: str) -> str:
    """
    Sanitise untrusted merchant input before it reaches the LLM.

    SECURITY: we (1) coerce to str, (2) strip ASCII/Unicode control characters
    that have no business in a spoken transaction, (3) collapse runs of
    whitespace, and (4) hard-cap the length. This bounds request size and keeps
    hostile bytes out of both the API call and our logs. It is NOT a
    prompt-injection cure — that is handled by schema-validating the output.
    """
    if not isinstance(raw, str):
        raw = str(raw)
    cleaned = "".join(ch for ch in raw if ch == " " or not _is_control(ch))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:_MAX_INPUT_CHARS]


def _build_messages(clean_input: str) -> list[dict[str, str]]:
    # The user utterance is wrapped in an explicit delimiter so the model
    # treats it as DATA to parse, not instructions to follow.
    user_content = (
        "Extract the transaction from the merchant statement below.\n"
        "<<<MERCHANT_STATEMENT\n"
        f"{clean_input}\n"
        "MERCHANT_STATEMENT>>>"
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

def _call_llm(url: str, api_key: str, model: str, messages: list[dict]) -> str:
    """POST to an OpenAI-compatible chat endpoint and return the message text."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": config.LLM_MAX_TOKENS,
        # Ask the provider to guarantee a JSON object where supported.
        "response_format": {"type": "json_object"},
    }
    resp = requests.post(
        url, headers=headers, json=payload, timeout=config.LLM_TIMEOUT_SECONDS
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _parse_and_validate(content: str) -> ExtractedTransaction:
    """
    Parse model output into a validated ExtractedTransaction.

    SECURITY: model output is untrusted. We isolate the JSON object and let
    Pydantic enforce types/bounds; on any failure the caller falls through to
    the next provider or the safe default.
    """
    text = (content or "").strip()
    # Strip markdown code fences if the model added them despite instructions.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    # Isolate the outermost JSON object.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in model output")
    payload = json.loads(text[start : end + 1])
    return ExtractedTransaction.model_validate(payload)

# ---------------------------------------------------------------------------
# Hardcoded demo safety net (DEMO RESILIENCE): if BOTH providers fail we still
# return a valid transaction so a live demo never crashes. Matches the
# "Mama Chidi Rice Debt" preset.
# ---------------------------------------------------------------------------
def _demo_fallback() -> ExtractedTransaction:
    return ExtractedTransaction(
        txn_type="credit_sale",
        amount=45000,
        item="rice",
        quantity=3,
        counterparty="Mama Chidi",
        note="3 bags of rice on credit",
        confidence=1.0,
        pidgin_confirmation="I don record am. Mama Chidi carry 3 bags of rice, 45k, she go pay later.",
    )


def extract_transaction(raw_input: str) -> ExtractedTransaction:
    """
    Public entry point. Returns a validated ExtractedTransaction, ALWAYS.

    Order: Gemini -> Groq fallback -> hardcoded demo transaction.
    Never raises to the caller — the demo must not die on a network/API error.
    """
    clean_input = _sanitize_input(raw_input)
    messages = _build_messages(clean_input)

    # 1) Primary: Google Gemini (OpenAI-compatible endpoint)
    if config.has_gemini_key():
        try:
            content = _call_llm(
                config.GEMINI_BASE_URL, config.GEMINI_API_KEY, config.GEMINI_MODEL, messages
            )
            return _parse_and_validate(content)
        except Exception as exc:  # noqa: BLE001 — resilience over precision here
            # Log provider + error TYPE only. No PII, no response body.
            logger.warning("Gemini extraction failed (%s); trying Groq.", type(exc).__name__)
    else:
        logger.info("No Gemini key configured; trying Groq.")

    # 2) Fallback: Groq (same messages, same schema)
    if config.has_groq_key():
        try:
            content = _call_llm(
                config.GROQ_BASE_URL, config.GROQ_API_KEY, config.GROQ_MODEL, messages
            )
            return _parse_and_validate(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Groq extraction failed (%s); using demo fallback.", type(exc).__name__)
    else:
        logger.info("No Groq key configured; using demo fallback.")

    # 3) Safety net: never let the demo crash.
    logger.info("Returning hardcoded demo transaction.")
    return _demo_fallback()
