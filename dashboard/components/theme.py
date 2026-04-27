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
          function isSidebarOpen(){
            const sb = document.querySelector('section[data-testid="stSidebar"]');
            if (!sb) return false;
            const aria = sb.getAttribute('aria-expanded');
            if (aria !== null) return aria === 'true';
            const r = sb.getBoundingClientRect();
            return r.width > 50 && r.left >= -10;
          }
          function closeSidebar(){
            const candidates = [
              '[data-testid="stSidebarCollapseButton"] button',
              '[data-testid="stSidebarCollapseButton"]',
              '[data-testid="collapsedControl"]',
              'button[kind="headerNoPadding"]',
              'section[data-testid="stSidebar"] [data-testid="baseButton-headerNoPadding"]',
              'section[data-testid="stSidebar"] button[aria-label*="ollapse"]',
              'section[data-testid="stSidebar"] button[aria-label*="lose"]',
            ];
            for (const sel of candidates){
              const el = document.querySelector(sel);
              if (el){ el.click(); return true; }
            }
            return false;
          }
          // Close sidebar after any click inside the sidebar nav (option_menu, radio, buttons)
          document.addEventListener('click', (e) => {
            if (!isMobile()) return;
            const sb = e.target.closest('section[data-testid="stSidebar"]');
            if (!sb) return;
            // Ignore clicks on the collapse button itself
            if (e.target.closest('[data-testid="stSidebarCollapseButton"]')) return;
            // Detect a navigation/menu item click
            const navHit = e.target.closest(
              '.nav-link, [role="radio"], [role="menuitem"], [role="tab"], a, button, label'
            );
            if (!navHit) return;
            // Allow the form/state update to fire first
            setTimeout(() => { if (isSidebarOpen()) closeSidebar(); }, 120);
          }, true);

          // Backdrop: tap outside the sidebar to close it on mobile
          function ensureBackdrop(){
            if (!isMobile()) return;
            if (!isSidebarOpen()) {
              const ex = document.getElementById('ab-sb-backdrop');
              if (ex) ex.remove();
              return;
            }
            if (document.getElementById('ab-sb-backdrop')) return;
            const bd = document.createElement('div');
            bd.id = 'ab-sb-backdrop';
            bd.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:99;backdrop-filter:blur(2px);';
            bd.addEventListener('click', () => closeSidebar());
            document.body.appendChild(bd);
          }
          const mo = new MutationObserver(() => ensureBackdrop());
          mo.observe(document.body, {subtree:true, attributes:true, childList:true});
          window.addEventListener('resize', ensureBackdrop);
          setTimeout(ensureBackdrop, 500);

          // ---- Rebrand: replace any "Streamlit" / "Running..." text with "AlphaBot FX" ----
          function rebrand(){
            try {
              // Browser tab
              if (document.title && /streamlit/i.test(document.title)) {
                document.title = 'AlphaBot FX';
              }
              // Toasts / dialogs / status widgets
              const sel = 'div[role="alert"], div[role="dialog"], [data-testid="stToast"], [data-testid="stStatusWidget"], [data-testid="stConnectionStatus"], .stException, .stAlert';
              document.querySelectorAll(sel).forEach(node => {
                if (!node || !node.innerHTML) return;
                let html = node.innerHTML;
                let changed = false;
                // Phrases to rewrite
                const map = [
                  [/Streamlit server/gi,                'AlphaBot FX server'],
                  [/the Streamlit app/gi,               'AlphaBot FX'],
                  [/Streamlit app/gi,                   'AlphaBot FX'],
                  [/the server is not responding[^.<]*\.?/gi, 'Reconnecting to AlphaBot FX…'],
                  [/Connection error[^<]*?try again/gi, 'AlphaBot FX is reconnecting'],
                  [/Please wait\s*\.{0,3}/gi,           'AlphaBot FX is reconnecting…'],
                  [/Made with Streamlit/gi,             ''],
                  [/Streamlit/g,                        'AlphaBot FX'],
                ];
                for (const [re, rep] of map){
                  if (re.test(html)){ html = html.replace(re, rep); changed = true; }
                }
                if (changed) node.innerHTML = html;
              });
            } catch(e){}
          }
          const moBrand = new MutationObserver(rebrand);
          moBrand.observe(document.body, {subtree:true, childList:true, characterData:true});
          rebrand();
          setInterval(rebrand, 1500);
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
