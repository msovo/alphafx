"""Calendar Report — daily/weekly/monthly P/L heatmap and trade summary."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.components import page_header
from data.fx_rates import fmt_money, get_rate, display_currency
from journal.analytics import closed_trades


def _to_dt(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", utc=True)


def render() -> None:
    page_header("Calendar Report", "Daily P/L calendar, weekly summary, monthly totals")

    df = closed_trades()
    if df.empty:
        st.info("No closed trades yet — calendar will populate as the bot runs.")
        return

    df = df.copy()
    df["close_dt"] = _to_dt(df["close_time"])
    df = df.dropna(subset=["close_dt"])
    # Convert to SAST for grouping
    df["close_dt_sast"] = df["close_dt"].dt.tz_convert("Africa/Johannesburg")
    df["day"] = df["close_dt_sast"].dt.date
    df["pnl_usd"] = pd.to_numeric(df["pnl_usd"], errors="coerce").fillna(0.0)

    # ---- Month picker -----------------------------------------------------
    months = (
        df["close_dt_sast"].dt.to_period("M").drop_duplicates().sort_values(ascending=False)
    )
    month_labels = [str(m) for m in months]
    if not month_labels:
        st.info("No data to show.")
        return
    sel_label = st.selectbox("Month", month_labels, index=0, key="cal_month")
    sel_period = pd.Period(sel_label, "M")
    sel_year, sel_month = sel_period.year, sel_period.month

    month_df = df[df["close_dt_sast"].dt.to_period("M") == sel_period]
    daily = month_df.groupby("day").agg(
        pnl=("pnl_usd", "sum"),
        trades=("pnl_usd", "count"),
        wins=("pnl_usd", lambda s: int((s > 0).sum())),
    ).reset_index()
    by_day = {row["day"]: row for _, row in daily.iterrows()}

    # ---- KPI strip --------------------------------------------------------
    total_pnl = float(month_df["pnl_usd"].sum())
    n_trades = int(len(month_df))
    n_wins = int((month_df["pnl_usd"] > 0).sum())
    wr = (n_wins / n_trades * 100.0) if n_trades else 0.0
    best_day = daily.loc[daily["pnl"].idxmax()] if not daily.empty else None
    worst_day = daily.loc[daily["pnl"].idxmin()] if not daily.empty else None

    cur = display_currency()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"Month P/L ({cur})", fmt_money(total_pnl, signed=True))
    k2.metric("Trades", n_trades, f"{wr:.1f}% WR")
    k3.metric("Best day",
              fmt_money(best_day["pnl"], signed=True) if best_day is not None else "—",
              str(best_day["day"]) if best_day is not None else "")
    k4.metric("Worst day",
              fmt_money(worst_day["pnl"], signed=True) if worst_day is not None else "—",
              str(worst_day["day"]) if worst_day is not None else "")

    # ---- Calendar heatmap (Plotly) ---------------------------------------
    cal = calendar.Calendar(firstweekday=0)  # Monday-first
    weeks = cal.monthdatescalendar(sel_year, sel_month)
    rows = len(weeks)
    z, txt, hover = [], [], []
    for week in weeks:
        z_row, t_row, h_row = [], [], []
        for d in week:
            in_month = d.month == sel_month
            rec = by_day.get(d)
            if not in_month:
                z_row.append(None); t_row.append(""); h_row.append("")
                continue
            if rec is None:
                z_row.append(0.0)
                t_row.append(f"<b>{d.day}</b>")
                h_row.append(f"{d.strftime('%a %d %b %Y')}<br>No trades")
            else:
                pnl = float(rec["pnl"])
                z_row.append(pnl)
                t_row.append(
                    f"<b>{d.day}</b><br>"
                    f"<span style='font-size:11px'>{fmt_money(pnl, signed=True)}</span><br>"
                    f"<span style='font-size:10px;opacity:.7'>{int(rec['trades'])}t</span>"
                )
                h_row.append(
                    f"{d.strftime('%a %d %b %Y')}<br>"
                    f"P/L: {fmt_money(pnl, signed=True)}<br>"
                    f"Trades: {int(rec['trades'])} • Wins: {int(rec['wins'])}"
                )
        z.append(z_row); txt.append(t_row); hover.append(h_row)

    # Symmetric color scale around 0
    abs_max = max(daily["pnl"].abs().max() if not daily.empty else 1.0, 1.0)
    fig = go.Figure(go.Heatmap(
        z=z, text=txt, texttemplate="%{text}",
        hovertext=hover, hoverinfo="text",
        x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        y=[f"Wk {i+1}" for i in range(rows)][::-1],
        zmin=-abs_max, zmax=abs_max,
        colorscale=[
            [0.0, "#ff5d6a"],
            [0.45, "rgba(255,93,106,0.15)"],
            [0.5, "rgba(120,120,140,0.15)"],
            [0.55, "rgba(0,212,170,0.15)"],
            [1.0, "#00d4aa"],
        ],
        showscale=True,
        xgap=4, ygap=4,
    ))
    # Reverse so first week is at top
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        template="plotly_dark", height=80 + rows * 78,
        title=f"{sel_period.strftime('%B %Y')} — daily P/L (SAST)",
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cbd2e0"),
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit",
                    config={"displaylogo": False})

    # ---- Weekly bar -------------------------------------------------------
    month_df = month_df.copy()
    month_df["week"] = month_df["close_dt_sast"].dt.to_period("W").astype(str)
    weekly = month_df.groupby("week")["pnl_usd"].sum().reset_index()
    if not weekly.empty:
        rate_zar = get_rate("USDZAR") if cur == "ZAR" else None
        y_vals = (weekly["pnl_usd"] * rate_zar) if rate_zar else weekly["pnl_usd"]
        bar = go.Figure(go.Bar(
            x=weekly["week"], y=y_vals,
            marker_color=["#00d4aa" if v >= 0 else "#ff5d6a" for v in y_vals],
            text=[fmt_money(v, signed=True) for v in weekly["pnl_usd"]], textposition="outside",
        ))
        bar.update_layout(
            template="plotly_dark", height=260,
            title=f"Weekly P/L ({cur})",
            margin=dict(l=10, r=10, t=40, b=10),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#cbd2e0"),
        )
        st.plotly_chart(bar, use_container_width=True, theme="streamlit",
                        config={"displaylogo": False})

    # ---- Day drill-down ---------------------------------------------------
    st.markdown("#### Day drill-down")
    available_days = sorted(daily["day"].tolist(), reverse=True)
    if available_days:
        sel_day = st.selectbox("Pick a day", available_days,
                               format_func=lambda d: d.strftime("%a %d %b %Y"),
                               key="cal_day")
        day_trades = month_df[month_df["day"] == sel_day][
            ["close_dt_sast", "pair", "direction", "lots", "entry_price",
             "close_price", "pnl_usd", "rr_achieved", "session"]
        ].rename(columns={"close_dt_sast": "closed (SAST)"}).copy()
        day_trades["closed (SAST)"] = day_trades["closed (SAST)"].dt.strftime("%H:%M:%S")
        day_trades[f"P/L ({cur})"] = day_trades["pnl_usd"].apply(lambda v: fmt_money(v, signed=True))
        day_trades = day_trades.drop(columns=["pnl_usd"])
        st.dataframe(day_trades, use_container_width=True, hide_index=True)

    # ---- Monthly table & export -------------------------------------------
    st.divider()
    st.markdown("#### Daily summary table")
    summary = daily.copy()
    summary[f"P/L ({cur})"] = summary["pnl"].apply(lambda v: fmt_money(v, signed=True))
    summary = summary.drop(columns=["pnl"])
    summary = summary.rename(columns={
        "day": "Date", "trades": "Trades", "wins": "Wins",
    })
    st.dataframe(summary, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Export month CSV",
        summary.to_csv(index=False).encode("utf-8"),
        file_name=f"alphabot_{sel_label}_calendar.csv",
        mime="text/csv",
    )
