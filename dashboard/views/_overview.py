"""Overview / Home page."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config.settings import get_settings
from core.broker import get_broker
from core.state import get_state
from dashboard.components import page_header, progress_bar, status_pill
from data.news import next_high_impact_event
from data.session import detect_session


def _start_bot() -> None:
    from core.scheduler import get_scheduler
    get_scheduler().start()
    get_state().start()
    st.toast("Bot started", icon="⚡")


def _stop_bot() -> None:
    from core.scheduler import get_scheduler
    get_state().stop()
    get_scheduler().shutdown()
    st.toast("Bot stopped", icon="🛑")


def _close_all() -> None:
    broker = get_broker()
    for p in broker.positions():
        broker.close_position(p.ticket)
    st.toast("All positions closed", icon="✅")


def _render_status_hero(state, open_positions: int) -> None:
    """Big, glanceable banner: is the bot ON or OFF + last activity."""
    status = (state.status or "stopped").lower()
    mode = state.mode or "—"

    # Heartbeat → SAST
    hb_txt = "—"
    hb_age = "no heartbeat yet"
    if state.last_heartbeat:
        try:
            from datetime import datetime, timezone
            from utils.helpers import to_sast
            dt = datetime.fromisoformat(state.last_heartbeat.replace(" ", "T"))
            hb_txt = to_sast(dt).strftime("%H:%M:%S SAST")
            secs = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds()
            if secs < 60:
                hb_age = f"{int(secs)}s ago"
            elif secs < 3600:
                hb_age = f"{int(secs // 60)}m ago"
            else:
                hb_age = f"{int(secs // 3600)}h ago"
        except Exception:                                  # noqa: BLE001
            pass

    # Last closed trade (open positions are shown separately)
    last_trade_txt = "No closed trades yet"
    try:
        from journal.analytics import closed_trades
        df = closed_trades(limit=1)
        if not df.empty:
            row = df.iloc[0]
            pnl = float(row.get("pnl_usd", 0) or 0)
            pair = row.get("pair", "—")
            ct = str(row.get("close_time", ""))[:16].replace("T", " ")
            sign = "+" if pnl >= 0 else ""
            last_trade_txt = f"{pair} · {sign}{pnl:.2f} USD · {ct}"
        elif open_positions > 0:
            last_trade_txt = f"No closed trades yet ({open_positions} open)"
    except Exception:                                      # noqa: BLE001
        pass

    # Scheduler cadence shown in hero for transparency
    try:
        scan_every = int(get_settings().get("bot.scan_interval_minutes", 15))
    except Exception:                                      # noqa: BLE001
        scan_every = 15

    # Color/label per status
    palette = {
        "running":     ("#00d4aa", "BOT RUNNING",   "🟢", "rgba(0,212,170,0.18)"),
        "paused":      ("#ffd166", "BOT PAUSED",    "🟡", "rgba(255,209,102,0.18)"),
        "stopped":     ("#ff6b6b", "BOT STOPPED",   "🔴", "rgba(255,107,107,0.18)"),
        "kill_switch": ("#ff3b3b", "KILL SWITCH",   "🛑", "rgba(255,59,59,0.22)"),
    }
    color, label, dot_emoji, glow = palette.get(status, palette["stopped"])
    pulse = "ab-pulse" if status == "running" else ""

    html = f"""
    <style>
      @keyframes ab-pulse-anim {{
        0% {{ box-shadow: 0 0 0 0 {color}80; }}
        70% {{ box-shadow: 0 0 0 14px {color}00; }}
        100% {{ box-shadow: 0 0 0 0 {color}00; }}
      }}
      .ab-pulse .ab-status-dot {{ animation: ab-pulse-anim 1.6s infinite; }}
      .ab-status-hero {{
        display:flex; flex-wrap:wrap; align-items:center; gap:18px;
        padding:14px 18px; margin:6px 0 14px 0;
        border-radius:16px;
        background: linear-gradient(135deg, {glow}, rgba(255,255,255,0.02));
        border:1px solid {color}55;
        backdrop-filter: blur(10px);
      }}
      .ab-status-dot {{
        width:14px; height:14px; border-radius:50%;
        background:{color}; box-shadow:0 0 12px {color};
        flex-shrink:0;
      }}
      .ab-status-label {{
        font-weight:800; font-size:1.05rem; letter-spacing:.5px;
        color:{color}; text-transform:uppercase;
      }}
      .ab-status-meta {{
        display:flex; flex-wrap:wrap; gap:14px; margin-left:auto;
        font-size:.88rem; color:#cbd2e0;
      }}
      .ab-status-meta b {{ color:#fff; font-weight:600; }}
      .ab-status-meta .sep {{ opacity:.4; }}
      @media (max-width: 640px) {{
        .ab-status-meta {{ margin-left:0; width:100%; }}
      }}
    </style>
    <div class="ab-status-hero {pulse}">
      <span class="ab-status-dot"></span>
      <span class="ab-status-label">{label}</span>
      <span class="ab-status-meta">
        <span>Mode <b>{mode}</b></span><span class="sep">·</span>
                <span>Auto scan <b>{scan_every}m</b></span><span class="sep">·</span>
        <span>Open <b>{open_positions}</b></span><span class="sep">·</span>
        <span>Heartbeat <b>{hb_txt}</b> <span style="opacity:.6">({hb_age})</span></span><span class="sep">·</span>
        <span>Last trade <b>{last_trade_txt}</b></span>
      </span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render() -> None:
    page_header("Overview", "Live account, risk, sessions, and bot controls")

    s = get_settings()
    state = get_state().state
    broker = get_broker()
    info = broker.account_info()
    positions = broker.positions()

    # --- Bot status hero banner --------------------------------------------
    _render_status_hero(state, len(positions))

    if info is None:
        st.warning("Broker offline — connect MT5 (or running in Mock mode).")

    # --- KPI cards ----------------------------------------------------------
    from data.fx_rates import get_rate, fmt_money, fmt_money_from_account, display_currency
    zar_rate = get_rate("USDZAR")
    equity = info.equity if info else 0.0
    balance = info.balance if info else 0.0
    free = info.free_margin if info else 0.0
    acct_cur = (getattr(info, "currency", "USD") if info else "USD")
    cur = display_currency()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Equity ({cur})", fmt_money_from_account(equity, acct_cur),
              f"{fmt_money(state.daily_pnl, signed=True)} today")
    c2.metric(f"Balance ({cur})", fmt_money_from_account(balance, acct_cur))
    c3.metric(f"Free margin ({cur})", fmt_money_from_account(free, acct_cur))
    c4.metric("Open positions", len(positions),
              f"{state.daily_trades} trades today")

    # ZAR rate badge
    if zar_rate and cur == "ZAR" and acct_cur == "USD":
        st.markdown(
            f"<div class='ab-card' style='padding:8px 14px;margin:4px 0 12px 0;font-size:0.9em'>"
            f"🇿🇦 USD/ZAR <b>{zar_rate:.4f}</b> "
            f"<span class='sub'>· all values shown in ZAR</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # Broker mode visibility (prevents silent Mock fallback confusion)
    bname = getattr(broker, "name", "unknown").upper()
    if bname == "MOCK":
        st.warning("Broker mode: MOCK. Orders will not appear in MT5 until MT5 reconnects.")
    elif info:
        st.caption(f"Broker: {bname} • Account {info.login} @ {info.server} • Account currency: {acct_cur}")

    # --- DD bars ------------------------------------------------------------
    daily_limit = float(s.get("risk.daily_loss_limit_pct", 5.0))
    max_dd = float(s.get("risk.max_drawdown_pct", 10.0))
    dd_pct = state.daily_dd_pct / daily_limit * 100 if daily_limit else 0
    tdd_pct = state.total_dd_pct / max_dd * 100 if max_dd else 0
    dd_kind = "bad" if dd_pct >= 80 else ("warn" if dd_pct >= 50 else "")
    tdd_kind = "bad" if tdd_pct >= 80 else ("warn" if tdd_pct >= 50 else "")

    cA, cB = st.columns(2)
    with cA:
        st.markdown("**Daily drawdown**")
        st.markdown(progress_bar(dd_pct, dd_kind), unsafe_allow_html=True)
        st.caption(f"{state.daily_dd_pct:.2f}% used of {daily_limit:.2f}%")
    with cB:
        st.markdown("**Total drawdown**")
        st.markdown(progress_bar(tdd_pct, tdd_kind), unsafe_allow_html=True)
        st.caption(f"{state.total_dd_pct:.2f}% used of {max_dd:.2f}%")

    st.divider()

    # --- Controls + status --------------------------------------------------
    cc1, cc2, cc3, cc4 = st.columns([1, 1, 1, 2])
    cc1.button("▶️ Start", use_container_width=True, on_click=_start_bot, disabled=state.status == "running")
    cc2.button("⏸️ Stop", use_container_width=True, on_click=_stop_bot, disabled=state.status != "running")
    cc3.button("🔒 Close all", use_container_width=True, on_click=_close_all,
               disabled=len(positions) == 0)
    with cc4:
        sess = detect_session()
        ev = next_high_impact_event()
        if ev:
            from utils.helpers import fmt_sast
            ev_txt = (
                f"{fmt_sast(ev['datetime_utc'], '%H:%M')} SAST "
                f"({ev['datetime_utc'].strftime('%H:%M')} UTC) — "
                f"{ev['currency']} {ev['title']}"
            )
        else:
            ev_txt = "None scheduled"
        st.markdown(
            f"{status_pill('Session: ' + sess.upper(), 'good' if sess in ('london','new_york','overlap') else '')} "
            f"&nbsp;&nbsp;{status_pill('Mode: ' + state.mode)}",
            unsafe_allow_html=True,
        )
        st.caption(f"📅 Next high-impact: {ev_txt}")

    # --- Manual scan trigger -----------------------------------------------
    sc1, sc2 = st.columns([1, 4])
    if sc1.button("🔍 Run scan now", use_container_width=True):
        from core.pipeline import run_signal_scan
        with st.spinner("Scanning all pairs..."):
            try:
                results = run_signal_scan()
                st.success(f"Scan complete — {len(results)} candidates evaluated. See Signals tab.")
            except Exception as e:                          # noqa: BLE001
                st.error(f"Scan failed: {e}")
    sc2.caption("Manually triggers the full pipeline (data → indicators → ML → AI → execution gate).")

    st.divider()

    # --- Open positions table ----------------------------------------------
    st.markdown("#### Open positions")
    if not positions:
        st.info("No open positions.")
    else:
        rows = []
        for p in positions:
            tick = broker.symbol_info(p.symbol) or {}
            cur_px = tick.get("bid" if p.side == "BUY" else "ask", p.price_open)
            rows.append({
                "Ticket": p.ticket, "Pair": p.symbol, "Side": p.side,
                "Lots": p.volume, "Entry": p.price_open, "Current": cur_px,
                "SL": p.sl, "TP": p.tp,
                f"Floating P/L ({cur})": fmt_money(p.profit, signed=True),
                "Opened": p.open_time.strftime("%Y-%m-%d %H:%M"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
