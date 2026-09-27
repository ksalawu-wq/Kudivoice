# KudiVoice Frontend UI (`frontend/`)

This directory contains the user interface for **KudiVoice AI**, isolated from backend logic so frontend development proceeds smoothly without merge conflicts.

## Directory Structure
```
frontend/
├── app.py                # Main Streamlit dashboard application
├── presets.py            # 4 realistic Nigerian Pidgin scenarios & sample ledger state
├── styles/
│   └── theme.css         # African FinTech custom styling (Kudi Green + NVIDIA Glow)
└── components/
    ├── __init__.py
    ├── header.py         # Branding and merchant profile
    ├── voice_dock.py     # Preset scenario chips, transcript box, extraction trigger
    ├── ledger_view.py    # KPI metrics, transactions table, WhatsApp debt collection links
    └── credit_card.py    # KudiScore 300-850 gauge, risk tiers, and loan eligibility
```

## Running the Frontend
From the root of the repository:
```bash
streamlit run frontend/app.py
```

## Features
1. **1-Click Nigerian Market Scenarios:** Instant preset buttons (`Mama Chidi`, `Baba Tunde`, `Truck Offload`, `Brother Emeka`) for zero-latency judging demos.
2. **Extraction Review Card:** Displays item breakdown, cash collected vs. debt created, and spoken Pidgin voiceback confirmation.
3. **Dynamic Ledger:** Automatically updates today's sales, cash in hand, and customer debt balances upon confirmation.
4. **1-Click WhatsApp Debt Reminders:** Generates courteous localized WhatsApp payment reminders with one click.
5. **KudiScore™ Credit Rating:** Explains merchant alternative creditworthiness (300 to 850) for micro-lending partners like Kredete.
