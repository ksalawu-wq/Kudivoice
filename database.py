"""
KudiVoice data layer: SQLite ledger for informal traders.

Transaction contract (what nvidia_extractor.py should output; aliases in brackets are also accepted):
    txn_type      "sale" | "credit_sale" | "debt_payment" | "expense"   [type, transaction_type]
    amount        naira: number or string like "5,000", "N5k", "₦15k"     [amount_naira, total]
    item          optional, e.g. "rice"
    quantity      optional number                                        [qty]
    counterparty  customer/supplier name, REQUIRED for credit_sale and debt_payment
                                                                         [customer, supplier, name]
    note          optional free text                                     [description]
    confidence    optional 0..1 from the AI engine
    occurred_at   optional ISO datetime, defaults to now                 [date, timestamp]
Pydantic models are accepted directly (model_dump() is called for you).

Security / responsible-data notes (CompTIA narrative):
  * LLM output is treated as untrusted input. All SQL is parameterized, never string-built.
  * Strict validation: whitelisted transaction types, bounded amounts, length-capped text,
    control characters stripped, CHECK constraints enforced again at the database level.
  * Money stored as integer kobo, so no floating-point rounding errors in balances.
  * Raw voice/text transcripts are NOT stored unless KUDIVOICE_STORE_RAW=true (data minimisation).
  * delete_merchant() erases all of a merchant's data on request.
"""

from __future__ import annotations

import os
import random
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

DB_PATH = os.getenv("KUDIVOICE_DB", "kudivoice.db")
STORE_RAW_INPUT = os.getenv("KUDIVOICE_STORE_RAW", "false").lower() == "true"

TXN_TYPES = ("sale", "credit_sale", "debt_payment", "expense")
SOURCES = ("voice", "text", "manual", "demo")
MAX_AMOUNT_NAIRA = 50_000_000
MAX_TEXT_LEN = 120
MAX_RAW_LEN = 2000

_TYPE_ALIASES = {
    "cash_sale": "sale", "sold": "sale", "income": "sale",
    "credit": "credit_sale", "debt": "credit_sale", "owe": "credit_sale",
    "owing": "credit_sale", "debt_given": "credit_sale", "sale_on_credit": "credit_sale",
    "repayment": "debt_payment", "debt_recovery": "debt_payment",
    "payment_received": "debt_payment", "paid_back": "debt_payment",
    "purchase": "expense", "supplier_expense": "expense", "spent": "expense",
    "cost": "expense", "restock": "expense",
}
_CTRL = re.compile(r"[\x00-\x1f\x7f]")

SCHEMA = """
CREATE TABLE IF NOT EXISTS merchants (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    business_type TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id  INTEGER NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    txn_type     TEXT NOT NULL CHECK (txn_type IN ('sale','credit_sale','debt_payment','expense')),
    amount_kobo  INTEGER NOT NULL CHECK (amount_kobo > 0),
    item         TEXT,
    quantity     REAL,
    counterparty TEXT,
    note         TEXT,
    source       TEXT NOT NULL DEFAULT 'text' CHECK (source IN ('voice','text','manual','demo')),
    confidence   REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    raw_input    TEXT,
    occurred_at  TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_txn_merchant_time ON transactions (merchant_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_txn_counterparty  ON transactions (merchant_id, counterparty);
"""


# --------------------------------------------------------------------------- connection

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# --------------------------------------------------------------------------- helpers

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _iso(value) -> str:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None).isoformat(timespec="seconds")
    return str(value)


def _clean_text(value, max_len: int = MAX_TEXT_LEN):
    if value is None:
        return None
    text = re.sub(r"\s+", " ", _CTRL.sub(" ", str(value))).strip()
    return text[:max_len] or None


def _normalize_name(value):
    text = _clean_text(value)
    return text.title() if text else None


def naira(kobo: int) -> float:
    return round((kobo or 0) / 100, 2)


def parse_amount_naira(value) -> float:
    """Accepts 5000, 5000.0, "5,000", "₦5k", "N15K", "1.2m". Raises ValueError if unusable."""
    if isinstance(value, bool) or value is None:
        raise ValueError(f"Could not read amount: {value!r}")
    if isinstance(value, (int, float)):
        amount = float(value)
    else:
        text = str(value).strip().lower()
        for token in ("₦", "ngn", "naira", ",", " "):
            text = text.replace(token, "")
        if text.startswith("n"):
            text = text[1:]
        multiplier = 1
        if text.endswith("k"):
            multiplier, text = 1_000, text[:-1]
        elif text.endswith("m"):
            multiplier, text = 1_000_000, text[:-1]
        try:
            amount = float(text) * multiplier
        except ValueError:
            raise ValueError(f"Could not read amount: {value!r}") from None
    if not (0 < amount <= MAX_AMOUNT_NAIRA):  # also rejects NaN and inf
        raise ValueError(f"Amount out of range: {value!r}")
    return amount


def normalize_txn_type(value) -> str:
    key = re.sub(r"[\s\-]+", "_", str(value or "").strip().lower())
    key = _TYPE_ALIASES.get(key, key)
    if key not in TXN_TYPES:
        raise ValueError(f"Unknown transaction type: {value!r}")
    return key


def validate_transaction(data) -> dict:
    """Turn AI-extracted (untrusted) data into a clean, safe record. Raises ValueError."""
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif hasattr(data, "dict") and not isinstance(data, dict):
        data = data.dict()
    if not isinstance(data, dict):
        raise ValueError("Transaction must be a dict")

    def pick(*keys):
        for key in keys:
            if data.get(key) not in (None, ""):
                return data[key]
        return None

    txn_type = normalize_txn_type(pick("txn_type", "type", "transaction_type"))
    amount = parse_amount_naira(pick("amount", "amount_naira", "total"))

    quantity = pick("quantity", "qty")
    try:
        quantity = float(quantity) if quantity is not None else None
        if quantity is not None and not (0 < quantity < 1_000_000):
            quantity = None
    except (TypeError, ValueError):
        quantity = None

    confidence = pick("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
        if confidence is not None and not (0 <= confidence <= 1):
            confidence = None
    except (TypeError, ValueError):
        confidence = None

    occurred_at = pick("occurred_at", "date", "timestamp")
    try:
        parsed = datetime.fromisoformat(str(occurred_at)).replace(tzinfo=None) if occurred_at else None
        if parsed and parsed > datetime.now() + timedelta(days=1):
            parsed = None  # future dates are not trusted
        occurred_at = parsed.isoformat(timespec="seconds") if parsed else _now()
    except ValueError:
        occurred_at = _now()

    counterparty = _normalize_name(pick("counterparty", "customer", "supplier", "name"))
    if txn_type in ("credit_sale", "debt_payment") and not counterparty:
        raise ValueError("Credit sales and debt payments need a customer name")

    return {
        "txn_type": txn_type,
        "amount_kobo": round(amount * 100),
        "item": _clean_text(pick("item", "product")),
        "quantity": quantity,
        "counterparty": counterparty,
        "note": _clean_text(pick("note", "description")),
        "confidence": confidence,
        "occurred_at": occurred_at,
    }


def _row_to_dict(row) -> dict:
    record = dict(row)
    if "amount_kobo" in record:
        record["amount_naira"] = naira(record["amount_kobo"])
    return record


# --------------------------------------------------------------------------- merchants

def create_merchant(name: str, business_type: str | None = None) -> int:
    clean_name = _clean_text(name)
    if not clean_name:
        raise ValueError("Merchant name is required")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO merchants (name, business_type, created_at) VALUES (?, ?, ?)",
            (clean_name, _clean_text(business_type), _now()),
        )
        return cur.lastrowid


def get_merchant(merchant_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM merchants WHERE id = ?", (merchant_id,)).fetchone()
    return dict(row) if row else None


def list_merchants() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM merchants ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def delete_merchant(merchant_id: int) -> None:
    """Right to erasure: removes the merchant and every transaction (ON DELETE CASCADE)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM merchants WHERE id = ?", (merchant_id,))


# --------------------------------------------------------------------------- transactions

_INSERT_TXN = """
INSERT INTO transactions
    (merchant_id, txn_type, amount_kobo, item, quantity, counterparty, note,
     source, confidence, raw_input, occurred_at, created_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def _txn_params(merchant_id, txn, source, raw_input):
    raw = _clean_text(raw_input, MAX_RAW_LEN) if STORE_RAW_INPUT else None
    return (
        merchant_id, txn["txn_type"], txn["amount_kobo"], txn["item"], txn["quantity"],
        txn["counterparty"], txn["note"], source, txn["confidence"], raw,
        txn["occurred_at"], _now(),
    )


def add_transaction(merchant_id: int, data, source: str = "text", raw_input: str | None = None) -> dict:
    """Validate and store one transaction. Returns the saved record (with id and amount_naira)."""
    if source not in SOURCES:
        raise ValueError(f"Unknown source: {source!r}")
    txn = validate_transaction(data)
    with get_conn() as conn:
        cur = conn.execute(_INSERT_TXN, _txn_params(merchant_id, txn, source, raw_input))
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_dict(row)


def add_transactions(merchant_id: int, items: list, source: str = "text") -> list[dict]:
    """Store several at once (e.g. one voice note mentioning 3 sales). All-or-nothing."""
    if source not in SOURCES:
        raise ValueError(f"Unknown source: {source!r}")
    clean = [validate_transaction(item) for item in items]
    ids = []
    with get_conn() as conn:
        for txn in clean:
            ids.append(conn.execute(_INSERT_TXN, _txn_params(merchant_id, txn, source, None)).lastrowid)
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT * FROM transactions WHERE id IN ({placeholders}) ORDER BY id", ids
        ).fetchall() if ids else []
    return [_row_to_dict(r) for r in rows]


def delete_transaction(merchant_id: int, txn_id: int) -> bool:
    """Undo a wrong entry. Scoped to merchant_id so one merchant can't delete another's data."""
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM transactions WHERE id = ? AND merchant_id = ?", (txn_id, merchant_id)
        )
    return cur.rowcount > 0


def get_transactions(merchant_id: int, since=None, until=None, limit: int | None = None) -> list[dict]:
    sql = "SELECT * FROM transactions WHERE merchant_id = ?"
    params: list = [merchant_id]
    if since is not None:
        sql += " AND occurred_at >= ?"
        params.append(_iso(since))
    if until is not None:
        sql += " AND occurred_at <= ?"
        params.append(_iso(until))
    sql += " ORDER BY occurred_at DESC, id DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_first_transaction_date(merchant_id: int) -> datetime | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT MIN(occurred_at) AS first FROM transactions WHERE merchant_id = ?", (merchant_id,)
        ).fetchone()
    return datetime.fromisoformat(row["first"]) if row and row["first"] else None


# --------------------------------------------------------------------------- reports

def get_outstanding_debts(merchant_id: int) -> list[dict]:
    """Who owes the merchant money, biggest first. Feeds the WhatsApp reminder button."""
    sql = """
    SELECT counterparty,
           SUM(CASE WHEN txn_type = 'credit_sale'  THEN amount_kobo ELSE 0 END) AS given,
           SUM(CASE WHEN txn_type = 'debt_payment' THEN amount_kobo ELSE 0 END) AS paid,
           MAX(occurred_at) AS last_activity
    FROM transactions
    WHERE merchant_id = ? AND counterparty IS NOT NULL
      AND txn_type IN ('credit_sale', 'debt_payment')
    GROUP BY counterparty
    HAVING given - paid > 0
    ORDER BY given - paid DESC
    """
    with get_conn() as conn:
        rows = conn.execute(sql, (merchant_id,)).fetchall()
    now = datetime.now()
    return [
        {
            "counterparty": r["counterparty"],
            "owed_naira": naira(r["given"] - r["paid"]),
            "last_activity": r["last_activity"],
            "days_since_activity": (now - datetime.fromisoformat(r["last_activity"])).days,
        }
        for r in rows
    ]


def get_ledger_summary(merchant_id: int, since=None) -> dict:
    sql = """
    SELECT txn_type, COALESCE(SUM(amount_kobo), 0) AS total, COUNT(*) AS n
    FROM transactions WHERE merchant_id = ?
    """
    params: list = [merchant_id]
    if since is not None:
        sql += " AND occurred_at >= ?"
        params.append(_iso(since))
    sql += " GROUP BY txn_type"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()

    totals = {t: 0 for t in TXN_TYPES}
    count = 0
    for r in rows:
        totals[r["txn_type"]] = r["total"]
        count += r["n"]
    cash_in = totals["sale"] + totals["debt_payment"]
    outstanding = sum(d["owed_naira"] for d in get_outstanding_debts(merchant_id))
    return {
        "cash_sales": naira(totals["sale"]),
        "credit_given": naira(totals["credit_sale"]),
        "debt_collected": naira(totals["debt_payment"]),
        "expenses": naira(totals["expense"]),
        "cash_in": naira(cash_in),
        "net_cash": naira(cash_in - totals["expense"]),
        "transaction_count": count,
        "outstanding_debt": round(outstanding, 2),  # always all-time, since debts carry over
    }


def get_daily_totals(merchant_id: int, since=None) -> list[dict]:
    """Per-day cash in vs expenses, ready for a Streamlit line/bar chart."""
    sql = """
    SELECT substr(occurred_at, 1, 10) AS day,
           SUM(CASE WHEN txn_type IN ('sale', 'debt_payment') THEN amount_kobo ELSE 0 END) AS cash_in,
           SUM(CASE WHEN txn_type = 'expense' THEN amount_kobo ELSE 0 END) AS expenses,
           COUNT(*) AS n
    FROM transactions WHERE merchant_id = ?
    """
    params: list = [merchant_id]
    if since is not None:
        sql += " AND occurred_at >= ?"
        params.append(_iso(since))
    sql += " GROUP BY day ORDER BY day"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {"date": r["day"], "cash_in": naira(r["cash_in"]), "expenses": naira(r["expenses"]),
         "transactions": r["n"]}
        for r in rows
    ]


# --------------------------------------------------------------------------- demo data

def seed_demo_merchant(name: str = "Mama Tolu Foodstuff", days: int = 45, seed: int = 7) -> int:
    """Create a realistic trader with `days` of history so KudiScore has something to score.
    Deterministic (same seed, same data). Leaves Baba Sule overdue and Mama Chidi owing for rice."""
    rng = random.Random(seed)
    merchant_id = create_merchant(name, "foodstuff")
    items = [("rice", 1500, 9000), ("beans", 1200, 6000), ("garri", 800, 4000),
             ("palm oil", 2000, 12000), ("tomatoes", 500, 3500), ("indomie carton", 9000, 14000)]
    customers = ["Oga Emeka", "Baba Sule", "Aunty Ngozi", "Mama Chidi"]
    suppliers = ["Alhaji Musa", "Mile 12 Supplier"]
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    owed = {c: 0 for c in customers}
    records = []

    def at(day, hour_lo=7, hour_hi=19):
        return (day + timedelta(hours=rng.randint(hour_lo, hour_hi), minutes=rng.randint(0, 59))).isoformat()

    for d in range(days - 2):
        day = start + timedelta(days=d)
        if day.weekday() == 6 or rng.random() < 0.15:  # closed Sundays, some sick/market days
            continue
        for _ in range(rng.randint(3, 7)):
            item, lo, hi = rng.choice(items)
            records.append({"txn_type": "sale", "amount": round(rng.randint(lo, hi), -2),
                            "item": item, "occurred_at": at(day)})
        if d % 2 == 0:
            records.append({"txn_type": "expense", "amount": round(rng.randint(25000, 60000), -3),
                            "item": "restock", "counterparty": rng.choice(suppliers),
                            "occurred_at": at(day, 6, 8)})
        if rng.random() < 0.3:
            who = rng.choice(customers[:3])
            amount = round(rng.randint(3000, 15000), -2)
            owed[who] += amount
            records.append({"txn_type": "credit_sale", "amount": amount, "item": rng.choice(items)[0],
                            "counterparty": who, "occurred_at": at(day)})
        for who, amount_owed in owed.items():
            if amount_owed > 0 and rng.random() < 0.1:
                paid = amount_owed if rng.random() < 0.5 else round(amount_owed / 2, -2)
                owed[who] -= paid
                records.append({"txn_type": "debt_payment", "amount": paid, "counterparty": who,
                                "occurred_at": at(day)})

    # Demo hooks: Baba Sule's overdue debt (drags the score down until collected) and
    # Mama Chidi's rice on credit two days ago (recent, so it gets the grace period).
    records.append({"txn_type": "credit_sale", "amount": 60000, "item": "rice", "quantity": 4,
                    "counterparty": "Baba Sule", "note": "4 bags of rice for his canteen",
                    "occurred_at": (start + timedelta(days=days - 21, hours=11)).isoformat()})
    records.append({"txn_type": "credit_sale", "amount": 15000, "item": "rice", "quantity": 1,
                    "counterparty": "Mama Chidi", "note": "half bag of rice",
                    "occurred_at": (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds")})
    add_transactions(merchant_id, records, source="demo")
    return merchant_id
