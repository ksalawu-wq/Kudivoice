# KudiVoice Frontend Web Application (`frontend/`)

A modern, responsive African FinTech single-page web application built with **HTML5, CSS3, and JavaScript**.

## Directory Structure
```
frontend/
├── index.html        # Main web dashboard interface
├── css/
│   └── style.css     # African FinTech design system & animations
├── js/
│   ├── presets.js    # 4 realistic Nigerian Pidgin scenarios & sample ledger state
│   └── app.js        # Reactive client-side application logic & WhatsApp URL generator
└── README.md
```

## How to Preview the UI

### Option 1: Direct in Browser (Zero Setup)
Simply double-click `frontend/index.html` or drag and drop it into Google Chrome.

### Option 2: Live Server or Local Python HTTP Server
Run a lightweight HTTP server from the project directory:
```bash
python -m http.server 8000 --directory frontend
```
Then open: **`http://localhost:8000`**

## Interactive Features Included
1. **1-Click Nigerian Market Scenarios:** Tap any of the 4 scenario chips (`Mama Chidi`, `Baba Tunde`, `Truck Offload`, `Brother Emeka`) to instantly populate realistic Pidgin text.
2. **AI Extraction Simulation & Preview:** Renders an itemized extraction card showing cash collected vs. debt created, along with a spoken Pidgin confirmation.
3. **Dynamic Ledger Engine:** Clicking "Confirm & Post to Live Ledger" prepends the new transaction, recalculates total revenue/debts, and dynamically boosts the KudiScore.
4. **1-Click WhatsApp Collection Links:** Generates pre-filled, courteous Nigerian merchant debt reminders (`https://wa.me/...`).
5. **KudiScore™ Alternative Credit Gauge:** Displays a visual 300–850 rating with working capital loan limits.
