# 🎙️ KudiVoice AI
> **Voice-to-Ledger & Micro-Credit Profiler for Africa's Informal Traders**  
> *Built for the GOMYCODE × NVIDIA Hackathon ("Come Build with AI")*

---

## 🌍 The Problem in Nigeria & Africa
Over **80% of employment and daily retail transactions in Sub-Saharan Africa occur in the informal sector** (open markets like Balogun, Alaba International, and Bodija). 
- **Unstructured Records:** Merchants track transactions in paper notebooks or mental memory.
- **Credit Lockout:** Because cash flow cannot be independently verified, traditional banks refuse working capital loans, locking traders into predatory lending cycles.
- **Debt Leakage:** Merchants regularly extend informal credit ("buy now, pay later") to regular customers, losing track of receivables and suffering cash flow crises.

---

## ⚡ The Solution: KudiVoice AI
**KudiVoice AI** transforms informal spoken vernacular into formal financial power. A merchant simply taps one button and speaks naturally in **Nigerian Pidgin or English**.

1. **Unstructured Vernacular Parsing:** Captures natural market speech (e.g., *"I sell three bags of mama gold rice to Mama Chidi for 75k, she pay 50k cash, balance 25k next Friday"*).
2. **AI Extraction:** Converts spoken inputs into structured double-entry ledger records (Cash sales, Customer debts, Expenses).
3. **Automated WhatsApp Debt Collections:** 1-click courteous WhatsApp payment reminder links to recover overdue customer credit.
4. **Alternative Credit Scoring (KudiScore™):** An objective 300–850 creditworthiness rating that translates transaction velocity into verifiable working capital loan limits with partners like **Kredete**.

---

## 🏗️ Repository Architecture
The repository is modularly structured so frontend and backend development proceed in parallel:

```
Kudivoice/
├── .gitignore            # Strict isolation for .env, sqlite, and build files
├── .env.example          # Safe environment template for teammates
├── README.md             # Project documentation & judging guide
├── vercel.json           # Turnkey Vercel Edge deployment config
├── api.py                # Unified FastAPI server & REST API (serves frontend + API)
├── config.py             # Central configuration reader
├── schemas.py            # Pydantic data contracts
├── database.py           # Local SQLite ledger engine
├── credit_scorer.py      # KudiScore 300-850 mathematical formula
├── nvidia_extractor.py   # AI entity extraction engine
├── docs/                 # Hackathon documentation, pitch scripts & CompTIA log
│   └── comptia_skills_log.md
└── frontend/             # 🎨 UI / Frontend Dashboard (Impeccable Craft Edition)
    ├── index.html        # Main web interface
    ├── css/
    │   └── style.css     # African FinTech theme & animations
    ├── js/
    │   ├── presets.js    # Realistic Nigerian market test scenarios
    │   └── app.js        # Waveform canvas, audio synthesis & reactive ledger
    └── README.md
```

---

## 🚀 Quickstart

### 1. Preview the Web App Directly
Open `frontend/index.html` in Google Chrome.

### 2. Run the Full-Stack Server
```bash
python api.py
```
Open **`http://localhost:8000`** in your browser.

### 3. Deploy to Vercel
Connect this GitHub repo to [Vercel](https://vercel.com/new). Vercel reads `vercel.json` and deploys automatically!
