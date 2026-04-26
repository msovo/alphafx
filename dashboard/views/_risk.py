"""Risk Monitor page."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from config.settings import get_settings
from core.state import get_state
from dashboard.components import page_header
from journal.db import query
from risk.guardian import update_drawdowns


def _gauge(value: float, limit: float, title: str) -> go.Figure:
    return go.Figure(go.Indicator(
        mode="gauge+number",
        value=value, number={"suffix": "%"},
        title={"text": title, "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, max(limit, 1)]},
            "bar": {"color": "#00d4aa" if value < limit*0.5 else "#ffb648" if value < limit*0.8 else "#ff5d6a"},
            "steps": [
                {"range": [0, limit*0.5], "color": "rgba(0,212,170,0.15)"},
                {"range": [limit*0.5, limit*0.8], "color": "rgba(255,182,72,0.15)"},
                {"range": [limit*0.8, limit], "color": "rgba(255,93,106,0.15)"},
            ],
            "threshold": {"line": {"color": "#ff5d6a", "width": 3}, "value": limit},
        },
    )).update_layout(template="plotly_dark", height=260, margin=dict(l=10, r=10, t=40, b=10),
                     paper_bgcolor="rgba(0,0,0,0)")


def render() -> None:
    page_header("Risk Monitor", "Real-time risk gates and drawdown gauges")
    s = get_settings()
    update_drawdowns()
    state = get_state().state

    c1, c2 = st.columns(2)
    c1.plotly_chart(_gauge(state.daily_dd_pct, float(s.get("risk.daily_loss_limit_pct", 5.0)),
                           "Daily drawdown"), use_container_width=True)
    c2.plotly_chart(_gauge(state.total_dd_pct, float(s.get("risk.max_drawdown_pct", 10.0)),
                           "Total drawdown"), use_container_width=True)

    st.markdown("#### Active risk rules")
    rules = [
        ("Risk per trade", f"{s.get('risk.risk_pct_per_trade')}%", "—"),
        ("Max concurrent trades", s.get("risk.max_concurrent_trades"), state.open_positions),
        ("Max daily trades", s.get("risk.max_daily_trades"), state.daily_trades),
        ("Daily loss limit", f"{s.get('risk.daily_loss_limit_pct')}%", f"{state.daily_dd_pct:.2f}%"),
        ("Max drawdown", f"{s.get('risk.max_drawdown_pct')}%", f"{state.total_dd_pct:.2f}%"),
        ("News block ±", f"{s.get('prop_firm.news_block_before_min')}/{s.get('prop_firm.news_block_after_min')} min", ""),
    ]
    st.table({"Rule": [r[0] for r in rules], "Limit": [r[1] for r in rules], "Current": [r[2] for r in rules]})

    st.divider()
    st.markdown("#### Drawdown history")
    dd = query("SELECT timestamp, daily_dd, total_dd, equity FROM account_snapshots ORDER BY id DESC LIMIT 500")
    if not dd.empty:
        st.line_chart(dd.set_index("timestamp")[["daily_dd", "total_dd"]])

    st.markdown("#### Kill-switch event log")
    events = query("SELECT timestamp, level, category, message FROM events WHERE level IN ('CRITICAL','ERROR','WARNING') ORDER BY id DESC LIMIT 50")
    if events.empty:
        st.success("No risk incidents recorded.")
    else:
        st.dataframe(events, use_container_width=True, hide_index=True)
