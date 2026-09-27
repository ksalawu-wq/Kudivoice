"""
app.py — KudiVoice AI Streamlit dashboard.

Ties the whole pipeline together for a live demo:
    merchant utterance  ->  extract_transaction()  (Gemini -> Groq -> demo)
                        ->  db.add_transaction()    (validated, kobo-safe SQLite)
                        ->  compute_kudiscore()      (explainable 300-850 + grade + loan)

PANELS
  1. Input dock: type/paste an utterance, or fire one of 4 offline-safe presets.
  2. Live transaction feed: newest ledger entries as cards.
  3. Debt book: who owes money, each with a one-tap WhatsApp reminder.
  4. KudiScore panel: 300-850 gauge, risk grade A/B/C, and a max-loan ceiling.

SECURITY / PRIVACY DESIGN
  * Secrets: API keys are read ONLY through config.py (.env), never hardcoded
    here and never rendered — the sidebar shows a boolean "configured?" badge,
    not the key. See config.secrets_status().
  * Untrusted input: the utterance is sanitised inside the extractor and the
    model's output is schema-validated before it can reach SQL (parameterised).
  * No PII in the schema: WhatsApp needs a phone number, but per the data-
    minimisation rule phones are NEVER stored. DEMO_PHONES below is a UI-only
    lookup for the scripted demo customers; a real customer with no known phone
    simply shows "No phone recorded" instead of a button.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import quote

import streamlit as st

import config
import credit_scorer as cs
import database as db
from nvidia_extractor import extract_transaction

# --- UI-only demo phone book -------------------------------------------------
# NOT part of the database schema (see module docstring). Keyed by the customer
# name as the ledger stores it (title-cased). Matching is case-insensitive with
# a substring fallback so the seeded "Oga Emeka" still resolves to "emeka".
DEMO_PHONES = {
    "mama chidi": "+2348012345678",
    "emeka": "+2348098765432",
}

# --- Four offline-safe preset utterances (one per transaction type) ----------
# Each is a realistic Pidgin/English sentence. When the LLM providers are
# unreachable the extractor returns a valid demo transaction anyway (DEMO
# RESILIENCE), so these buttons never crash a live demo.
PRESETS = [
    {"label": "Mama Chidi — rice on credit", "icon": "📝",
     "utterance": "Mama Chidi carry 3 bags of rice, 45k, she go pay later"},
    {"label": "Cash sale — palm oil", "icon": "💰",
     "utterance": "I sell 2 bottles of palm oil, 12,500, cash sharp sharp"},
    {"label": "Restock — beans", "icon": "📦",
     "utterance": "I buy one bag of beans for 45000 from Alhaji Musa"},
    {"label": "Oga Emeka — balance me", "icon": "✅",
     "utterance": "Oga Emeka don balance me 5000"},
]

# Icon + human label per canonical txn_type, for the feed cards.
TXN_META = {
    "sale": ("💰", "Cash sale"),
    "credit_sale": ("📝", "Credit sale"),
    "debt_payment": ("✅", "Debt payment"),
    "expense": ("📦", "Expense"),
}


def _demo_phone(counterparty: str | None) -> str | None:
    """Resolve a UI-only demo phone for a customer name, or None (not stored)."""
    if not counterparty:
        return None
    key = counterparty.strip().lower()
    if key in DEMO_PHONES:
        return DEMO_PHONES[key]
    for name, phone in DEMO_PHONES.items():  # substring fallback ("Oga Emeka")
        if name in key:
            return phone
    return None


def _wa_link(phone: str, text: str) -> str:
    """Build a wa.me deep link. Digits only in the path; message URL-encoded."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"https://wa.me/{digits}?text={quote(text)}"


def _money(naira: float) -> str:
    return f"₦{naira:,.0f}"


@st.cache_resource
def _bootstrap() -> None:
    """Create the schema once per server process (cached across reruns)."""
    db.init_db()


def _active_merchant() -> int:
    """Return the selected merchant id, seeding the demo trader on first run so
    the dashboard always has something to show (DEMO RESILIENCE)."""
    if "merchant_id" not in st.session_state:
        merchants = db.list_merchants()
        if not merchants:
            st.session_state.merchant_id = db.seed_demo_merchant()
        else:
            st.session_state.merchant_id = merchants[0]["id"]
    return st.session_state.merchant_id


def _record(utterance: str, source: str) -> None:
    """Extract one transaction from an utterance and persist it. Never raises —
    the extractor always returns a schema-valid transaction, and any storage
    error is surfaced to the user rather than crashing the demo."""
    merchant_id = _active_merchant()
    try:
        txn = extract_transaction(utterance)
        # raw_input is passed through; database.py stores it ONLY if
        # KUDIVOICE_STORE_RAW=true (data minimisation, off by default).
        saved = db.add_transaction(merchant_id, txn, source=source, raw_input=utterance)
        st.session_state.last_confirm = {
            "pidgin": txn.pidgin_confirmation,
            "saved": saved,
        }
    except Exception as exc:  # noqa: BLE001 — show a friendly message, keep the app up
        st.session_state.last_confirm = {"error": type(exc).__name__}


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(page_title="KudiVoice AI", page_icon="🎙️", layout="wide")
_bootstrap()

st.markdown(
    """
    <style>
      .kv-card {border:1px solid #e6e6e6;border-radius:12px;padding:12px 14px;
                margin-bottom:10px;background:#ffffff;}
      .kv-muted {color:#8a8a8a;font-size:0.85rem;}
      .kv-amt {font-size:1.05rem;font-weight:600;}
      .kv-gauge {height:16px;border-radius:8px;position:relative;margin:8px 0 4px;
                 background:linear-gradient(90deg,#e5484d 0%,#f5a623 50%,#30a46c 100%);}
      .kv-gauge .kv-mark {position:absolute;top:-6px;width:4px;height:28px;
                 background:#111;border-radius:2px;transform:translateX(-50%);}
      .kv-scalerow {display:flex;justify-content:space-between;
                 font-size:0.75rem;color:#8a8a8a;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar — merchant selection, language, and a secret-safe provider badge
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("🎙️ KudiVoice AI")
    st.caption("Voice-to-Ledger & Credit Profiler for Nigerian traders")

    merchants = db.list_merchants()
    if merchants:
        ids = [m["id"] for m in merchants]
        current = _active_merchant()
        idx = ids.index(current) if current in ids else 0
        chosen = st.selectbox(
            "Trader", ids, index=idx,
            format_func=lambda i: next(m["name"] for m in merchants if m["id"] == i),
        )
        st.session_state.merchant_id = chosen

    with st.expander("➕ Add / reset trader"):
        new_name = st.text_input("New trader name", key="new_name")
        if st.button("Create", use_container_width=True) and new_name.strip():
            st.session_state.merchant_id = db.create_merchant(new_name.strip())
            st.rerun()
        if st.button("Load demo trader", use_container_width=True):
            st.session_state.merchant_id = db.seed_demo_merchant()
            st.rerun()

    lang = st.radio("Reminder / tips language", ["en", "pcm"],
                    format_func=lambda x: "English" if x == "en" else "Pidgin",
                    horizontal=True)

    st.divider()
    status = config.secrets_status()  # booleans only — never the key values
    st.caption("**AI providers configured**")
    st.write(f"{'🟢' if status['gemini'] else '⚪'} Gemini (primary)")
    st.write(f"{'🟢' if status['groq'] else '⚪'} Groq (fallback)")
    if not (status["gemini"] or status["groq"]):
        st.caption("No keys set — presets still work via the offline demo net.")

merchant_id = _active_merchant()
merchant = db.get_merchant(merchant_id) or {"name": "Trader"}
merchant_name = merchant["name"]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("KudiVoice AI")
st.caption(f"Recording for **{merchant_name}** · say it or type it, we keep the books.")

left, right = st.columns([3, 2], gap="large")

# ---------------------------------------------------------------------------
# LEFT — input dock, presets, and the live transaction feed
# ---------------------------------------------------------------------------
with left:
    st.subheader("① Record a transaction")
    utterance = st.text_area(
        "Type what happened (Pidgin or English)",
        placeholder="e.g. Mama Chidi carry 3 bags of rice, 45k, she go pay later",
        height=90, key="utterance_box",
    )
    if st.button("➕ Record it", type="primary", use_container_width=True):
        if utterance.strip():
            _record(utterance.strip(), source="text")
            st.rerun()
        else:
            st.warning("Type a transaction first, or tap a preset below.")

    st.caption("Or fire a scripted demo (works offline):")
    pcols = st.columns(2)
    for i, preset in enumerate(PRESETS):
        with pcols[i % 2]:
            if st.button(f"{preset['icon']} {preset['label']}",
                         key=f"preset_{i}", use_container_width=True):
                _record(preset["utterance"], source="voice")
                st.rerun()

    # Confirmation / error banner from the most recent record action.
    confirm = st.session_state.pop("last_confirm", None)
    if confirm:
        if "error" in confirm:
            st.error(f"Couldn't save that one ({confirm['error']}). Try again.")
        else:
            saved = confirm["saved"]
            st.success(f"🗣️ {confirm['pidgin']}")
            st.caption(f"Saved: {saved['txn_type']} · {_money(saved['amount_naira'])}"
                       + (f" · {saved['counterparty']}" if saved['counterparty'] else ""))

    st.subheader("② Live ledger")
    txns = db.get_transactions(merchant_id, limit=12)
    if not txns:
        st.info("No transactions yet. Record one above to get started.")
    for t in txns:
        icon, label = TXN_META.get(t["txn_type"], ("•", t["txn_type"]))
        who = f" · {t['counterparty']}" if t["counterparty"] else ""
        what = f" · {t['item']}" if t["item"] else ""
        when = t["occurred_at"][:16].replace("T", " ")
        c1, c2 = st.columns([6, 1])
        with c1:
            st.markdown(
                f"<div class='kv-card'>{icon} <b>{label}</b> "
                f"<span class='kv-amt'>{_money(t['amount_naira'])}</span>{who}{what}"
                f"<br><span class='kv-muted'>{when} · via {t['source']}</span></div>",
                unsafe_allow_html=True,
            )
        with c2:
            # Undo a mis-recorded entry. Scoped to this merchant in the DB layer.
            if st.button("🗑", key=f"del_{t['id']}", help="Delete this entry"):
                db.delete_transaction(merchant_id, t["id"])
                st.rerun()

# ---------------------------------------------------------------------------
# RIGHT — KudiScore panel and the debt book
# ---------------------------------------------------------------------------
with right:
    st.subheader("③ KudiScore")
    result = cs.compute_kudiscore(merchant_id)

    if result["status"] != "ok":
        st.info(result["band_message"])
    else:
        score = result["kudiscore"]
        # Gauge marker position: 300 -> 0%, 850 -> 100%.
        pct = max(0, min(100, round((score - cs.SCORE_MIN) / cs.SCORE_SPAN * 100)))
        m1, m2, m3 = st.columns(3)
        m1.metric("KudiScore", f"{score}", help="Credit-readiness on a 300–850 scale")
        m2.metric("Grade", f"{result['risk_grade']}", result["band"])
        m3.metric("Max loan", _money(result["max_loan_ngn"]))
        st.markdown(
            f"<div class='kv-gauge'><div class='kv-mark' style='left:{pct}%'></div></div>"
            "<div class='kv-scalerow'><span>300</span><span>575</span>"
            "<span>850</span></div>",
            unsafe_allow_html=True,
        )
        st.caption(result["explanation"])

        with st.expander("How this score is built (and what it never uses)"):
            for c in result["components"]:
                st.progress(
                    c["points"] / c["max_points"] if c["max_points"] else 0.0,
                    text=f"{c['label']} — {c['points']}/{c['max_points']} · {c['metric']}",
                )
            st.caption("Never used: " + ", ".join(result["fairness"]["never_used"]))

        if result["recommendations"]:
            st.markdown("**How to raise your score**")
            tip_key = "tip_pcm" if lang == "pcm" else "tip_en"
            for r in result["recommendations"]:
                st.markdown(f"- {r[tip_key]} _(up to +{r['potential_gain']} pts)_")

    st.subheader("④ Debt book")
    debtors = result["debtors"]
    if not debtors:
        st.success("No outstanding debts. 🎉")
    for d in debtors:
        overdue = d["days_since_activity"] >= cs.GRACE_DAYS
        flag = "🔴" if overdue else "🟡"
        st.markdown(
            f"<div class='kv-card'>{flag} <b>{d['counterparty']}</b> owes "
            f"<span class='kv-amt'>{_money(d['owed_naira'])}</span>"
            f"<br><span class='kv-muted'>Last activity {d['days_since_activity']} "
            f"day(s) ago</span></div>",
            unsafe_allow_html=True,
        )
        phone = _demo_phone(d["counterparty"])
        if phone:
            text = cs.whatsapp_reminder_text(d, merchant_name, lang=lang)
            st.link_button("💬 Send WhatsApp reminder", _wa_link(phone, text),
                           use_container_width=True)
        else:
            # No phone stored (data minimisation) — no button, just a note.
            st.markdown("<span class='kv-muted'>No phone recorded</span>",
                        unsafe_allow_html=True)

st.divider()
st.caption("KudiVoice AI · scores use only ledger behaviour, never name, gender, "
           "location, language, or how the entry was typed. Keys stay in .env.")
