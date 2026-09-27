"""
schemas.py — Pydantic v2 data models for KudiVoice AI.

DATA CONTRACT: `database.py` is the single source of truth for the shape of a
transaction (see its module docstring). `ExtractedTransaction` mirrors that
contract exactly, so the LLM extractor has a typed, validated target and its
output can be handed straight to `database.add_transaction()` — which calls
`model_dump()` on it for you.

SECURITY NOTE:
  * LLM output is UNTRUSTED input. Validating and coercing it against this typed
    schema is a defensive boundary that stops malformed or injected structures
    from reaching SQL or the UI.
  * The transaction-type and money parsers are IMPORTED from `database.py`, so
    the schema and the ledger can never disagree about the allowed vocabulary or
    how an amount like "45k" / "₦5,000" is read.
  * `str_strip_whitespace` plus explicit `max_length` bounds cap every free-text
    field — a simple guard against oversized or abusive payloads.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Reuse the ledger's own vocabulary + parsers so there is exactly one definition
# of "what is a valid transaction type" and "how do we read a naira amount".
from database import normalize_txn_type, parse_amount_naira

# The four transaction classes KudiVoice understands — identical to the ledger's
# TXN_TYPES so the extractor prompt, this schema, and the DB all agree.
TransactionType = Literal["sale", "credit_sale", "debt_payment", "expense"]


class ExtractedTransaction(BaseModel):
    """
    Canonical structured representation of ONE merchant utterance.

    Produced by the LLM extractor, validated here, then persisted via
    `database.add_transaction()` (accepts this model directly).

    Amount semantics (one figure per transaction, matching the ledger):
      * sale         -> cash received now
      * credit_sale  -> value of goods taken on credit (becomes the debt)
      * debt_payment -> amount the customer repaid
      * expense      -> amount spent (e.g. restocking from a supplier)
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    txn_type: TransactionType
    amount: float = Field(..., gt=0, description="Transaction amount in NGN (see class docstring).")
    item: Optional[str] = Field(default=None, max_length=120, description="Main good, e.g. 'rice'.")
    quantity: Optional[float] = Field(default=None, description="Units, e.g. 3 (bags). Null if unknown.")
    counterparty: Optional[str] = Field(
        default=None, max_length=120, description="Customer or supplier name."
    )
    note: Optional[str] = Field(default=None, max_length=120, description="Short free text.")
    confidence: Optional[float] = Field(default=None, description="Model confidence 0..1, or null.")
    pidgin_confirmation: str = Field(
        default="I don record am.",
        max_length=200,
        description="Short Pidgin confirmation echoed back to the merchant (UI only; DB ignores it).",
    )

    @field_validator("txn_type", mode="before")
    @classmethod
    def _normalize_type(cls, v):
        # Reuse the ledger's normaliser so aliases ("debt_recovery", "restock",
        # "sale_on_credit", ...) collapse to the canonical set. Raises on an
        # unknown type -> surfaces as a validation error, so the extractor falls
        # through to the next provider / the safe default.
        return normalize_txn_type(v)

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v):
        # Reuse the ledger's money parser so "45k", "₦5,000", "1.2m" all work and
        # the same 0 < amount <= 50m bounds apply. Raises on unusable input.
        return parse_amount_naira(v)

    @field_validator("quantity", mode="before")
    @classmethod
    def _clean_quantity(cls, v):
        # Forgiving on this optional field: a bad or out-of-range quantity becomes
        # null rather than rejecting the whole transaction (mirrors the DB layer).
        if v is None or v == "":
            return None
        try:
            q = float(v)
        except (TypeError, ValueError):
            return None
        return q if 0 < q < 1_000_000 else None

    @field_validator("confidence", mode="before")
    @classmethod
    def _clean_confidence(cls, v):
        if v is None or v == "":
            return None
        try:
            c = float(v)
        except (TypeError, ValueError):
            return None
        return c if 0 <= c <= 1 else None

    @field_validator("counterparty", "item", "note")
    @classmethod
    def _empty_to_none(cls, v: Optional[str]) -> Optional[str]:
        # Normalise "" (and whitespace-only, already stripped) to None so the
        # DB stores a clean NULL instead of an empty string.
        if v is None:
            return None
        return v or None

    @model_validator(mode="after")
    def _require_counterparty(self) -> "ExtractedTransaction":
        # Mirror the ledger rule: credit sales and debt payments must name the
        # customer, otherwise the debt book cannot attribute them.
        if self.txn_type in ("credit_sale", "debt_payment") and not self.counterparty:
            raise ValueError("credit_sale and debt_payment require a counterparty name")
        return self
