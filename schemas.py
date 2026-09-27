"""
schemas.py — Pydantic v2 data models for KudiVoice AI.

These schemas are the single source of truth for the shape of an extracted
transaction. The LLM (NVIDIA NIM / Groq) is instructed to emit JSON that
validates against `ExtractedTransaction`; anything that fails validation is
rejected before it can reach the database or the UI.

SECURITY NOTE:
  * LLM output is UNTRUSTED input. Validating and coercing it against a typed
    schema is a defensive boundary that stops malformed or injected structures
    from flowing into SQL / the UI.
  * `str_strip_whitespace` plus explicit `max_length` bounds cap the size of
    every free-text field — a simple guard against oversized/abusive payloads.
  * The phone validator strips everything except digits and a leading '+',
    neutralising any markup or text smuggled into that field.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# The four transaction classes KudiVoice understands. Kept as a module-level
# alias so the extractor prompt and the DB layer reference the same list.
TransactionType = Literal["SALE_CASH", "SALE_CREDIT", "EXPENSE", "DEBT_RECOVERY"]


class LineItem(BaseModel):
    """A single item within a transaction (e.g. '3 bags of rice')."""

    model_config = ConfigDict(str_strip_whitespace=True)

    item_name: str = Field(..., max_length=120, description="Name of the good sold/bought.")
    quantity: float = Field(default=1, ge=0, description="Number of units (bags, cartons, pcs).")
    unit_price: float = Field(default=0.0, ge=0, description="Price per unit in NGN.")
    total_amount: float = Field(default=0.0, ge=0, description="Line total in NGN.")

    @model_validator(mode="after")
    def _fill_total(self) -> "LineItem":
        # If the model provided quantity + unit_price but omitted the total,
        # derive it so downstream maths is consistent.
        if self.total_amount == 0 and self.quantity and self.unit_price:
            object.__setattr__(
                self, "total_amount", round(self.quantity * self.unit_price, 2)
            )
        return self


class ExtractedTransaction(BaseModel):
    """
    Canonical structured representation of one merchant utterance.
    Produced by the LLM extractor, validated here, then persisted.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    transaction_type: TransactionType
    party_name: str = Field(..., max_length=120, description="Customer or supplier name.")
    party_phone: Optional[str] = Field(default=None, max_length=20)
    items: list[LineItem] = Field(default_factory=list)
    amount_paid: float = Field(default=0.0, ge=0, description="Cash received now, in NGN.")
    debt_amount: float = Field(default=0.0, ge=0, description="Outstanding credit owed, in NGN.")
    due_date: Optional[str] = Field(
        default=None, max_length=40, description="Free-form due date, e.g. 'next week'."
    )
    pidgin_confirmation: str = Field(
        default="I don record am.",
        max_length=200,
        description="Short Pidgin confirmation echoed back to the merchant.",
    )

    @field_validator("party_phone")
    @classmethod
    def _clean_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # Keep only digits and a single leading '+'; drop injected text/markup.
        cleaned = "".join(ch for ch in v if ch.isdigit() or ch == "+")
        return cleaned or None

    @field_validator("party_name")
    @classmethod
    def _non_empty_name(cls, v: str) -> str:
        return v.strip() or "Unknown"
