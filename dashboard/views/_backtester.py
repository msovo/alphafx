"""Backtester page."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from backtest.engine import run_backtest
from config.settings import get_settings
from dashboard.components import page_header


def render() -> None:
    page_header("Backtester", "Replay strategy on historical data")
    s = get_settings()
    pairs = list(s.get("bot.pairs", ["EURUSD"]))
    c1, c2, c3 = st.columns(3)
    pair = c1.selectbox("Pair", pairs)
    tf = c2.selectbox("Timeframe", ["M15", "M30", "H1", "H4"], index=0)
    bars = c3.slider("Bars", 200, 2000, 800, 100)

    if st.button("🚀 Run backtest", type="primary"):
        with st.spinner("Running..."):
            res = run_backtest(pair, tf, n=bars)
        m = res["metrics"]
        st.success(f"{m.get('trades',0)} trades · win-rate {m.get('win_rate',0)}% · "
                   f"net {m.get('total_return_pips',0)}")
        if res["equity"]:
            df = pd.DataFrame(res["equity"])
            fig = px.line(df, x="time", y="equity", title="Backtest equity",
                          template="plotly_dark", color_discrete_sequence=["#00d4aa"])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              margin=dict(l=10, r=10, t=40, b=10), height=380)
            st.plotly_chart(fig, use_container_width=True)
        if res["trades"]:
            st.dataframe(pd.DataFrame(res["trades"]), use_container_width=True, hide_index=True)
