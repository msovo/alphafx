"""Reusable Streamlit UI helpers."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

CSS_FILE = Path(__file__).parent.parent / "static" / "style.css"


def inject_css() -> None:
    if CSS_FILE.exists():
        st.markdown(f"<style>{CSS_FILE.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    # Mobile viewport meta + auto-close sidebar on mobile after nav click
    st.markdown(
        """
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
        <script>
        (function(){
          if (window.__abMobileNavBound) return;
          window.__abMobileNavBound = true;
          const isMobile = () => window.matchMedia('(max-width: 768px)').matches;
          function closeSidebar(){
            const btn =
              document.querySelector('[data-testid="stSidebarCollapseButton"]') ||
              document.querySelector('button[kind="headerNoPadding"]') ||
              document.querySelector('section[data-testid="stSidebar"] button');
            if (btn) btn.click();
          }
          document.addEventListener('click', (e) => {
            if (!isMobile()) return;
            const link = e.target.closest('section[data-testid="stSidebar"] .nav-link, section[data-testid="stSidebar"] [role="radio"]');
            if (link) setTimeout(closeSidebar, 80);
          }, true);
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )


def status_pill(label: str, kind: str = "") -> str:
    cls = f"ab-pill {kind}".strip()
    return f"<span class='{cls}'>{label}</span>"


def progress_bar(pct: float, kind: str = "") -> str:
    pct = max(0.0, min(100.0, float(pct)))
    cls = f"ab-bar {kind}".strip()
    return f"<div class='{cls}'><div style='width:{pct:.1f}%'></div></div>"


def card(title: str, value: str, sub: str = "", kind: str = "") -> str:
    return (
        f"<div class='ab-card'>"
        f"<h4>{title}</h4>"
        f"<div style='font-size:1.6rem;font-weight:700'>{value}</div>"
        f"<div class='sub'>{sub}</div>"
        f"</div>"
    )


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f"## {title}")
    if subtitle:
        st.caption(subtitle)
