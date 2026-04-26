# AlphaBot FX

> Enterprise-grade autonomous foreign-exchange trading platform.
> AI-driven, prop-firm aware, fully auditable, and continuously self-learning.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![Status](https://img.shields.io/badge/status-active--development-yellow)]()
[![Stack](https://img.shields.io/badge/stack-Streamlit%20%7C%20MT5%20%7C%20Gemini%20%7C%20RandomForest-success)]()

---

## ✨ What is AlphaBot FX?

AlphaBot FX is a fully autonomous Forex / Indices / Gold trading co-pilot that:

- 🔌 Connects to **MetaTrader 5** for real-time price feeds and order execution
- 📐 Runs a **multi-timeframe confluence engine** (H4 → H1 → M15) with 7+ indicators, S&R levels, FVGs, and candlestick patterns
- 🌲 Applies a **Random Forest ML filter** that learns from your own trade history
- 🧠 Routes every candidate through **Google Gemini AI** for human-style reasoning
- 🛡️ Enforces **prop-firm risk rules** with a hard kill-switch
- 📲 Sends **Telegram alerts** with one-tap approve/reject buttons
- 📊 Presents everything in a **mobile-responsive Streamlit dashboard**
- 🔁 **Continuously retrains** itself every Sunday from new trade outcomes

## 🚀 Quick Start

```powershell
# 1. Clone & enter
cd C:\Users\Msovo\Documents\alphabot-fx

# 2. Create venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install
pip install -r requirements.txt

# 4. Configure
copy .env.example .env
# → fill in MT5_*, GEMINI_API_KEY, TELEGRAM_*

# 5. Launch dashboard
streamlit run dashboard/app.py

# 6. (Optional) Run the autonomous scheduler
python main.py
```

## 🧩 Project Layout

See [Architecture overview](docs/ARCHITECTURE.md) and section 5 of the BRS.

```
alphabot-fx/
├── main.py                # Scheduler entry point
├── dashboard/             # Streamlit UI (8 pages, mobile responsive)
├── core/                  # Broker, scheduler, global state
├── data/                  # Market feed, news, sessions
├── analysis/              # Indicators, S&R, MTF confluence
├── ml/                    # Random Forest learner
├── ai/                    # Gemini reasoning layer
├── risk/                  # Lot sizing, kill-switch, trade mgmt
├── execution/             # Order placement & modes
├── journal/               # SQLite trade log + analytics
├── notifications/         # Telegram bot
└── backtest/              # Vectorised backtester
```

## 🔧 Operating Modes

| Mode | Behaviour |
|------|-----------|
| `signal_only` | Generates and shows signals — never trades. Safe for development. |
| `manual_confirm` | Sends signal to Telegram, requires "Take Trade" tap. |
| `full_auto` | Executes immediately when AI ≥ confidence threshold. |

Switch modes live from **Settings → Bot Settings**.

## 🛡️ Safety

- All credentials live in `.env` (gitignored).
- Kill-switch trips at 80% (warning) / 100% (hard stop) of daily-loss or max-DD.
- Trades blocked ±30 min around red-folder news.
- Heartbeat watchdog + automatic MT5 reconnect.

## 🧪 Phase Map

- **Phase 1** — Core engine, dashboard, MT5, Telegram
- **Phase 2** — Gemini reasoning + Manual Confirm mode
- **Phase 3** — ML retraining loop
- **Phase 4** — Backtester, weekly reports, news filter
- **Phase 5** — VPS hardening
- **Phase 6** — Multi-user SaaS (FastAPI + Stripe)

---

© 2026 AlphaBot FX. For private use during development.
