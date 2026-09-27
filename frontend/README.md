# KudiVoice Frontend Web Application (`frontend/`)

A modern, responsive African FinTech single-page web application built with **HTML5, CSS3, and JavaScript** following **Impeccable Craft** design principles.

## Directory Structure
```
frontend/
├── index.html        # Main web dashboard interface
├── css/
│   └── style.css     # African FinTech design system & animations
├── js/
│   ├── presets.js    # 4 realistic Nigerian Pidgin scenarios & sample ledger state
│   └── app.js        # Waveform canvas, audio synthesis & reactive ledger logic
└── README.md
```

## How to Preview the UI

### Option 1: Direct in Browser (Zero Setup)
Simply double-click `frontend/index.html` or drag and drop it into Google Chrome.

### Option 2: Run Full-Stack Server
From the root of the repository:
```bash
python app.py
```
Then open: **`http://localhost:8000`**

## Interactive Features Included
1. **Live Audio Waveform Canvas:** Animated sound frequency visualizer while recording.
2. **Dialect Switcher:** Fast toggles for *Nigerian Pidgin*, *Yoruba*, *Hausa*, and *English*.
3. **1-Click Nigerian Market Scenarios:** Tap any of the 4 scenario chips (`Mama Chidi`, `Baba Tunde`, `Truck Offload`, `Brother Emeka`) to instantly populate realistic Pidgin text.
4. **Digital Market POS Receipt:** Renders line items, cash paid, debt created, and a **"🔊 Play Voice"** button that speaks the Nigerian Pidgin confirmation aloud using browser speech synthesis!
5. **Dynamic Ledger Engine:** Automatically updates today's sales, cash in hand, and customer debt balances upon confirmation.
6. **1-Click WhatsApp Collection Links:** Generates pre-filled, courteous Nigerian merchant debt reminders (`https://wa.me/...`).
7. **KudiScore™ Alternative Credit Gauge:** Displays a visual 300–850 rating with working capital loan limits.
