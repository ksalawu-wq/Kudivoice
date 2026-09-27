"""
KudiScore: an explainable 300-850 credit-readiness score (FICO-style range) built
from a trader's own ledger, plus a risk grade (A/B/C) and a max-loan recommendation in NGN.

Design principles (use these in the bias audit / responsible AI section):
  * Uses ONLY ledger behaviour: activity, cash flow, debt collection, stability, record depth.
  * NEVER uses name, gender, location, language or dialect, or input method (voice vs text),
    so a Pidgin or Hausa speaker is scored exactly like an English speaker with the same ledger.
  * Fully explainable: every component reports its raw metric and the points it earned.
  * Too little data returns "insufficient_data", NOT a low score. New traders are not
    punished for being new.
  * Recent credit (last 7 days) is not counted against the trader, since it isn't overdue yet.
  * Deterministic and rule-based: no LLM in the scoring path, same ledger gives the same score.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta

import database as db

WINDOW_DAYS = 30
GRACE_DAYS = 7
MIN_TRANSACTIONS = 10
MIN_ACTIVE_DAYS = 5

WEIGHTS = {
    "consistency": 25,
    "cash_flow": 25,
    "debt_recovery": 20,
    "stability": 15,
    "record_depth": 15,
}
LABELS = {
    "consistency": "Trading consistency",
    "cash_flow": "Cash flow health",
    "debt_recovery": "Debt collection",
    "stability": "Sales stability",
    "record_depth": "Record history",
}
# --- KudiScore scale (Kredete-aligned, FICO-style range) -------------------
# Components are still weighted out of 100 internally (transparent, easy to
# audit), then mapped proportionally onto the 300-850 range that lenders expect.
SCORE_MIN = 300
SCORE_MAX = 850
SCORE_SPAN = SCORE_MAX - SCORE_MIN  # 550

# Risk-grade cut-offs on the 300-850 scale:
#   300-499 -> C (building), 500-699 -> B (moderate), 700-850 -> A (strong)
GRADES = [
    (700, "A", "Strong", "Ready to approach lenders"),
    (500, "B", "Moderate", "Close to lender-ready — a few gaps to close"),
    (SCORE_MIN, "C", "Building", "Keep recording to strengthen your profile"),
]

# Max-loan recommendation: a fraction of ~monthly cash inflow that scales with
# the score (0.2x at the floor, up to 1.0x at the top). Grounded in the trader's
# OWN realised cash flow — never demographics — and capped for prudence.
LOAN_FACTOR_MIN = 0.2
LOAN_FACTOR_MAX = 1.0
LOAN_ROUND_NGN = 1_000
LOAN_CAP_NGN = 2_000_000
FAIRNESS = {
    "inputs_used": ["transaction dates", "transaction amounts", "transaction types",
                    "debt given and collected"],
    "never_used": ["name", "gender", "age", "location", "tribe or ethnicity", "religion",
                   "language or dialect", "voice vs text input"],
}


def _money(value: float) -> str:
    return f"₦{value:,.0f}"


def _scale(value: float, worst: float, best: float) -> float:
    """Map value onto 0..1 where `worst` gives 0 and `best` gives 1 (works in either direction)."""
    if best == worst:
        return 1.0
    return max(0.0, min(1.0, (value - worst) / (best - worst)))


def _to_kudiscore(fraction: float) -> int:
    """Map internal achievement (0..1) onto the 300-850 KudiScore range."""
    return round(SCORE_MIN + max(0.0, min(1.0, fraction)) * SCORE_SPAN)


def _grade(kudiscore: float):
    """Return (grade_letter, band_word, band_message) for a 300-850 score."""
    for floor, letter, word, message in GRADES:
        if kudiscore >= floor:
            return letter, word, message
    last = GRADES[-1]
    return last[1], last[2], last[3]


def _max_loan_ngn(monthly_cash_in: float, fraction: float) -> int:
    """Suggested loan ceiling: a score-scaled fraction of monthly cash inflow,
    rounded to the nearest ₦1,000 and capped for prudence. Uses only the trader's
    own realised cash flow, so the recommendation is explainable and demographic-free."""
    factor = LOAN_FACTOR_MIN + (LOAN_FACTOR_MAX - LOAN_FACTOR_MIN) * max(0.0, min(1.0, fraction))
    amount = max(0.0, monthly_cash_in) * factor
    amount = round(amount / LOAN_ROUND_NGN) * LOAN_ROUND_NGN
    return int(min(amount, LOAN_CAP_NGN))


def _status(fraction: float) -> str:
    return "good" if fraction >= 0.75 else "fair" if fraction >= 0.4 else "weak"


def compute_kudiscore(merchant_id: int, window_days: int = WINDOW_DAYS, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    since = now - timedelta(days=window_days)

    txns = db.get_transactions(merchant_id, since=since, until=now)
    active_days = len({t["occurred_at"][:10] for t in txns})
    base = {
        "merchant_id": merchant_id,
        "window_days": window_days,
        "period": {"from": since.date().isoformat(), "to": now.date().isoformat()},
        "generated_at": now.isoformat(timespec="seconds"),
        "fairness": FAIRNESS,
    }

    if len(txns) < MIN_TRANSACTIONS or active_days < MIN_ACTIVE_DAYS:
        msg = (f"Record at least {MIN_TRANSACTIONS} transactions over {MIN_ACTIVE_DAYS} "
               f"different days to unlock your KudiScore. You have {len(txns)} across "
               f"{active_days} day(s).")
        return {
            **base,
            "status": "insufficient_data",
            "kudiscore": None,
            "score_100": None,
            "risk_grade": None,
            "band": "Not enough records yet",
            "band_message": msg,
            "max_loan_ngn": 0,
            "explanation": msg,
            "components": [],
            "recommendations": [],
            "debtors": db.get_outstanding_debts(merchant_id),
        }

    window = db.get_ledger_summary(merchant_id, since=since)
    lifetime = db.get_ledger_summary(merchant_id)
    recent_credit = db.get_ledger_summary(merchant_id, since=now - timedelta(days=GRACE_DAYS))["credit_given"]
    daily = db.get_daily_totals(merchant_id, since=since)
    first_date = db.get_first_transaction_date(merchant_id) or now
    debtors = db.get_outstanding_debts(merchant_id)

    # 1. Consistency: share of days with at least one record (80%+ is full marks, ~6 days a week)
    active_ratio = active_days / window_days
    f_consistency = _scale(active_ratio, 0.2, 0.8)

    # 2. Cash flow: margin of cash in over expenses (30%+ is full marks, -10% or worse is zero)
    cash_in, expenses = window["cash_in"], window["expenses"]
    margin = (cash_in - expenses) / cash_in if cash_in else -1.0
    f_cash = _scale(margin, -0.1, 0.3)

    # 3. Debt collection: share of credit given that is NOT overdue (recent credit gets grace)
    total_given = lifetime["credit_given"]
    overdue = max(0.0, lifetime["outstanding_debt"] - recent_credit)
    recovery = 1.0 if total_given == 0 else max(0.0, 1 - overdue / total_given)
    f_debt = _scale(recovery, 0.5, 0.95)

    # 4. Stability: coefficient of variation of daily cash in (lower = steadier)
    daily_in = [d["cash_in"] for d in daily if d["cash_in"] > 0]
    if len(daily_in) >= 2 and statistics.mean(daily_in) > 0:
        cv = statistics.pstdev(daily_in) / statistics.mean(daily_in)
    else:
        cv = 1.5
    f_stability = _scale(cv, 1.2, 0.3)

    # 5. Record depth: how long they've been recording (90 days = full) and volume (60 txns/month = full)
    history_days = max(0, (now - first_date).days)
    f_depth = 0.5 * _scale(history_days, 0, 90) + 0.5 * _scale(len(txns), 0, 60)

    fractions = {
        "consistency": f_consistency,
        "cash_flow": f_cash,
        "debt_recovery": f_debt,
        "stability": f_stability,
        "record_depth": f_depth,
    }
    metrics = {
        "consistency": f"Active on {active_days} of the last {window_days} days",
        "cash_flow": f"{_money(cash_in)} in, {_money(expenses)} out ({margin:.0%} margin)",
        "debt_recovery": (f"{_money(overdue)} overdue of {_money(total_given)} credit given"
                          if total_given else "No credit given to customers"),
        "stability": f"Daily sales vary by {cv:.0%} on average",
        "record_depth": f"{history_days} days of records, {len(txns)} entries this month",
    }

    components = []
    for key, weight in WEIGHTS.items():
        frac = fractions[key]
        components.append({
            "key": key,
            "label": LABELS[key],
            "points": round(weight * frac, 1),
            "max_points": weight,
            "status": _status(frac),
            "metric": metrics[key],
        })
    raw = sum(c["points"] for c in components)   # internal 0..100 (weights sum to 100)
    score_100 = round(raw)
    kudiscore = _to_kudiscore(raw / 100)
    grade, band, band_message = _grade(kudiscore)

    # Repayment capacity: normalise window cash-in to a 30-day figure, then size
    # the recommendation by the score. Only the merchant's own cash flow feeds this.
    monthly_cash_in = cash_in * (30 / window_days) if window_days else cash_in
    max_loan = _max_loan_ngn(monthly_cash_in, raw / 100)
    explanation = (
        f"KudiScore {kudiscore}/850 — Grade {grade} ({band}). "
        f"Suggested loan ceiling {_money(max_loan)}, sized to about {_money(monthly_cash_in)} "
        f"monthly cash flow and your debt-collection record."
    )

    context = {
        "overdue": overdue,
        "debtors": debtors,
        "margin": margin,
        "active_days": active_days,
        "window_days": window_days,
        "history_days": history_days,
    }
    weak = sorted((c for c in components if c["status"] != "good"),
                  key=lambda c: c["max_points"] - c["points"], reverse=True)
    recommendations = [_recommend(c, context) for c in weak[:3]]

    return {
        **base,
        "status": "ok",
        "kudiscore": kudiscore,
        "score_100": score_100,
        "risk_grade": grade,
        "band": band,
        "band_message": band_message,
        "max_loan_ngn": max_loan,
        "explanation": explanation,
        "components": components,
        "recommendations": recommendations,
        "debtors": debtors,
        "summary": {
            "cash_in": cash_in,
            "monthly_cash_in": round(monthly_cash_in, 2),
            "expenses": expenses,
            "net_cash": window["net_cash"],
            "outstanding_debt": lifetime["outstanding_debt"],
            "transactions": len(txns),
            "active_days": active_days,
        },
    }


def _recommend(component: dict, ctx: dict) -> dict:
    key = component["key"]
    gain = round(component["max_points"] - component["points"], 1)

    if key == "consistency":
        en = (f"You recorded on {ctx['active_days']} of {ctx['window_days']} days. Record every "
              "trading day, even small sales. Lenders want to see steady activity.")
        pcm = "Dey record your sales every day wey you open shop, even the small ones. Lenders wan see say business dey move steady."
    elif key == "cash_flow":
        en = (f"Your margin is {ctx['margin']:.0%}. Spending is close to what comes in. "
              "Check your restock costs and selling prices.")
        pcm = "Wetin you dey spend don near wetin you dey gain. Check how you dey buy stock and how you dey price your goods."
    elif key == "debt_recovery":
        late = [d for d in ctx["debtors"] if d["days_since_activity"] >= GRACE_DAYS] or ctx["debtors"]
        names = ", ".join(d["counterparty"] for d in late[:3]) or "customers"
        en = (f"{_money(ctx['overdue'])} is overdue from {names}. Collecting it raises your score. "
              "Send a WhatsApp reminder.")
        pcm = f"{names} still dey owe you {_money(ctx['overdue'])}. Collect am make your score go up. Send WhatsApp reminder."
    elif key == "stability":
        en = "Your daily sales go up and down a lot. Regular stock and fixed prices help steady them."
        pcm = "Your daily sales dey go up and down well well. Keep stock for shop always so customers no go waka."
    else:  # record_depth
        en = (f"You have {ctx['history_days']} days of records. Keep going to 3 months; lenders "
              "trust longer histories.")
        pcm = "Continue to dey record for at least 3 months. Lenders go trust you pass when dem see long record."

    return {"component": key, "label": component["label"], "potential_gain": gain, "tip_en": en, "tip_pcm": pcm}


def explain_score(result: dict, lang: str = "en") -> str:
    """Markdown summary for the dashboard. lang: 'en' or 'pcm' (Nigerian Pidgin)."""
    if result["status"] != "ok":
        return f"**{result['band']}**\n\n{result['band_message']}"
    lines = [
        f"### KudiScore: {result['kudiscore']}/850 — Grade {result['risk_grade']} ({result['band']})",
        result["band_message"],
        f"**Suggested loan ceiling:** {_money(result['max_loan_ngn'])}",
        "",
    ]
    for c in result["components"]:
        lines.append(f"- **{c['label']}**: {c['points']}/{c['max_points']} ({c['metric']})")
    if result["recommendations"]:
        lines += ["", "**How to raise your score:**"]
        tip_key = "tip_pcm" if lang == "pcm" else "tip_en"
        for r in result["recommendations"]:
            lines.append(f"- {r[tip_key]} (up to +{r['potential_gain']} points)")
    return "\n".join(lines)


def whatsapp_reminder_text(debtor: dict, merchant_name: str, lang: str = "en") -> str:
    """Polite reminder text for the WhatsApp button (URL-encode it for a wa.me link)."""
    amount = _money(debtor["owed_naira"])
    if lang == "pcm":
        return (f"Good day {debtor['counterparty']}, na {merchant_name} dey greet you. "
                f"Abeg remember the {amount} wey remain for your account. Thank you!")
    return (f"Good day {debtor['counterparty']}, this is {merchant_name}. "
            f"A gentle reminder about the {amount} balance on your account. Thank you!")


if __name__ == "__main__":
    import json
    import os
    import tempfile

    db.DB_PATH = os.path.join(tempfile.mkdtemp(), "kudivoice_test.db")
    db.init_db()
    mid = db.seed_demo_merchant()

    # The 4 demo scenarios, shaped like extractor output (messy amounts on purpose)
    demo = [
        {"type": "credit_sale", "amount": "₦8k", "item": "rice", "customer": "mama chidi",
         "confidence": 0.92},
        {"txn_type": "sale", "amount": "12,500", "item": "palm oil", "quantity": 2},
        {"txn_type": "expense", "amount": 45000, "item": "bag of beans", "supplier": "Alhaji Musa"},
        {"txn_type": "debt_recovery", "amount": "5000", "counterparty": "Oga Emeka"},
    ]
    for d in demo:
        saved = db.add_transaction(mid, d, source="voice", raw_input="(demo)")
        print(f"saved #{saved['id']}: {saved['txn_type']:<12} {_money(saved['amount_naira']):>9} "
              f"{saved['counterparty'] or ''}")

    # Security check: injection attempt is stored as plain text, table survives
    db.add_transaction(mid, {"txn_type": "sale", "amount": 100,
                             "item": "x'); DROP TABLE transactions;--"})
    for bad in [{"txn_type": "steal", "amount": 5}, {"txn_type": "sale", "amount": -500},
                {"txn_type": "credit_sale", "amount": 500}, {"txn_type": "sale", "amount": "lots"}]:
        try:
            db.add_transaction(mid, bad)
            print("NOT REJECTED:", bad)
        except ValueError as e:
            print("rejected:", e)

    result = compute_kudiscore(mid)
    print()
    print(f"KudiScore={result['kudiscore']}/850  Grade={result['risk_grade']}  "
          f"MaxLoan={_money(result['max_loan_ngn'])}")
    print(result["explanation"])
    print()
    print(explain_score(result))
    print()
    print(explain_score(result, lang="pcm").split("**How to raise your score:**")[-1])
    print("\nDebtors:", json.dumps(result["debtors"][:3], indent=1))
    print("\nReminder:", whatsapp_reminder_text(result["debtors"][0], "Mama Tolu Foodstuff", "pcm"))

    new_id = db.create_merchant("New Trader")
    print("\nNew trader:", compute_kudiscore(new_id)["band_message"])
