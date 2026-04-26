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


def render() -> None:
    page_header("Overview", "Live account, risk, sessions, and bot controls")

    s = get_settings()
    state = get_state().state
    broker = get_broker()
    info = broker.account_info()
    positions = broker.positions()

    if info is None:
        st.warning("Broker offline — connect MT5 (or running in Mock mode).")

    # --- KPI cards ----------------------------------------------------------
    from data.fx_rates import get_rate, fmt_money, display_currency
    zar_rate = get_rate("USDZAR")
    equity_usd = info.equity if info else 0.0
    balance_usd = info.balance if info else 0.0
    free_usd = info.free_margin if info else 0.0
    cur = display_currency()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Equity ({cur})", fmt_money(equity_usd),
              f"{fmt_money(state.daily_pnl, signed=True)} today")
    c2.metric(f"Balance ({cur})", fmt_money(balance_usd))
    c3.metric(f"Free margin ({cur})", fmt_money(free_usd))
    c4.metric("Open positions", len(positions),
              f"{state.daily_trades} trades today")

    # ZAR rate badge
    if zar_rate and cur == "ZAR":
        st.markdown(
            f"<div class='ab-card' style='padding:8px 14px;margin:4px 0 12px 0;font-size:0.9em'>"
            f"🇿🇦 USD/ZAR <b>{zar_rate:.4f}</b> "
            f"<span class='sub'>· all values shown in ZAR</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

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
