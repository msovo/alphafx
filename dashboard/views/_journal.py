"""Trade Journal page."""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from dashboard.components import page_header
from data.fx_rates import fmt_money, get_rate, display_currency
from journal.analytics import (
    by_pair, by_session, closed_trades, equity_curve, overall_metrics,
)


def render() -> None:
    page_header("Trade Journal", "All closed trades, performance and analytics")

    metrics = overall_metrics()
    cur = display_currency()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trades", metrics["trades"])
    c2.metric("Win rate", f"{metrics['win_rate']}%")
    c3.metric("Profit factor", metrics["profit_factor"])
    c4.metric(f"Total P/L ({cur})", fmt_money(metrics["total_pnl"], signed=True))

    eq = equity_curve()
    if not eq.empty:
        rate = get_rate("USDZAR") if cur == "ZAR" else None
        eq_disp = eq.copy()
        if rate:
            eq_disp["equity"] = eq_disp["equity"] * rate
        ylabel = f"Equity ({cur})"
        fig = px.line(eq_disp, x="close_time", y="equity",
                      title=f"Equity curve · {cur}",
                      template="plotly_dark", color_discrete_sequence=["#00d4aa"],
                      labels={"equity": ylabel})
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          margin=dict(l=10, r=10, t=40, b=10), height=380)
        st.plotly_chart(fig, use_container_width=True)

    cA, cB = st.columns(2)
    with cA:
        st.markdown("#### By pair")
        bp = by_pair()
        if not bp.empty:
            bp_disp = bp.copy()
            for col in ("total_pnl", "avg_pnl"):
                if col in bp_disp.columns:
                    bp_disp[col] = bp_disp[col].apply(lambda v: fmt_money(v, signed=True))
            st.dataframe(bp_disp, use_container_width=True, hide_index=True)
    with cB:
        st.markdown("#### By session")
        bs = by_session()
        if not bs.empty:
            bs_disp = bs.copy()
            for col in ("total_pnl", "avg_pnl"):
                if col in bs_disp.columns:
                    bs_disp[col] = bs_disp[col].apply(lambda v: fmt_money(v, signed=True))
            st.dataframe(bs_disp, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### All closed trades")
    df = closed_trades()
    if df.empty:
        st.info("No closed trades yet.")
        return
    df_disp = df.copy()
    if "pnl_usd" in df_disp.columns:
        df_disp[f"P/L ({cur})"] = df_disp["pnl_usd"].apply(lambda v: fmt_money(v, signed=True))
        df_disp = df_disp.drop(columns=["pnl_usd"])
    st.dataframe(df_disp, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Export CSV", df.to_csv(index=False).encode("utf-8"),
                       file_name="alphabot_trades.csv", mime="text/csv")
