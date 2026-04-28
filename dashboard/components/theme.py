"""Reusable Streamlit UI helpers."""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

CSS_FILE = Path(__file__).parent.parent / "static" / "style.css"


_JS_HELPERS = r"""
<script>
(function(){
  const D = window.parent.document;
  if (D.__abHelpersBound) return;
  D.__abHelpersBound = true;

  const isMobile = () => window.parent.matchMedia('(max-width: 768px)').matches;
  function isSidebarOpen(){
    const sb = D.querySelector('section[data-testid="stSidebar"]');
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
      'section[data-testid="stSidebar"] button[aria-label*="ollapse"]',
      'section[data-testid="stSidebar"] button[aria-label*="lose"]',
    ];
    for (const sel of candidates){
      const el = D.querySelector(sel);
      if (el){ el.click(); return true; }
    }
    return false;
  }

  function toggleSidebar(){
    const candidates = [
      '[data-testid="stSidebarCollapseButton"] button',
      '[data-testid="stSidebarCollapseButton"]',
      '[data-testid="collapsedControl"]',
      'button[kind="headerNoPadding"]',
      'section[data-testid="stSidebar"] button[aria-label*="ollapse"]',
      'section[data-testid="stSidebar"] button[aria-label*="lose"]',
      'button[aria-label*="Sidebar"]',
    ];
    for (const sel of candidates){
      const el = D.querySelector(sel);
      if (el){ el.click(); return true; }
    }
    return false;
  }

  function ensureMenuFab(){
    let fab = D.getElementById('ab-menu-fab');
    if (!fab){
      fab = D.createElement('button');
      fab.id = 'ab-menu-fab';
      fab.type = 'button';
      fab.setAttribute('aria-label', 'Toggle menu');
      fab.innerText = '☰';
      fab.style.cssText = [
        'position:fixed',
        'top:8px',
        'left:8px',
        'z-index:1400',
        'width:34px',
        'height:34px',
        'border-radius:10px',
        'border:1px solid rgba(0,212,170,.45)',
        'background:rgba(10,14,26,.88)',
        'color:#00d4aa',
        'font-size:18px',
        'line-height:30px',
        'cursor:pointer',
        'box-shadow:0 8px 20px rgba(0,0,0,.35)',
      ].join(';');
      fab.addEventListener('click', () => toggleSidebar());
      D.body.appendChild(fab);
    }
  }

  // Auto-close sidebar on nav click (mobile)
  D.addEventListener('click', (e) => {
    if (!isMobile()) return;
    const sb = e.target.closest('section[data-testid="stSidebar"]');
    if (!sb) return;
    if (e.target.closest('[data-testid="stSidebarCollapseButton"]')) return;
    const navHit = e.target.closest('.nav-link, [role="radio"], [role="menuitem"], [role="tab"], a, button, label');
    if (!navHit) return;
    setTimeout(() => { if (isSidebarOpen()) closeSidebar(); }, 120);
  }, true);

  // Tap-outside backdrop
  function ensureBackdrop(){
    if (!isMobile()) return;
    if (!isSidebarOpen()){
      const ex = D.getElementById('ab-sb-backdrop');
      if (ex) ex.remove();
      return;
    }
    if (D.getElementById('ab-sb-backdrop')) return;
    const bd = D.createElement('div');
    bd.id = 'ab-sb-backdrop';
    bd.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:99;backdrop-filter:blur(2px);';
    bd.addEventListener('click', () => closeSidebar());
    D.body.appendChild(bd);
  }
  new MutationObserver(ensureBackdrop).observe(D.body, {subtree:true, attributes:true, childList:true});
  window.parent.addEventListener('resize', ensureBackdrop);
  setTimeout(ensureBackdrop, 500);
  setTimeout(ensureMenuFab, 100);

  // Rebrand: hide "Streamlit" / connection toasts
  function rebrand(){
    try {
      if (D.title && /streamlit/i.test(D.title)) D.title = 'AlphaBot FX';
      const sel = 'div[role="alert"], div[role="dialog"], [data-testid="stToast"], [data-testid="stStatusWidget"], [data-testid="stConnectionStatus"], .stException, .stAlert';
      D.querySelectorAll(sel).forEach(node => {
        if (!node || !node.innerHTML) return;
        let html = node.innerHTML;
        let changed = false;
        const map = [
          [/Streamlit server/gi,           'AlphaBot FX server'],
          [/the Streamlit app/gi,          'AlphaBot FX'],
          [/Streamlit app/gi,              'AlphaBot FX'],
          [/the server is not responding[^.<]*\.?/gi, 'Reconnecting to AlphaBot FX\u2026'],
          [/Connection error[^<]*?try again/gi, 'AlphaBot FX is reconnecting'],
          [/Made with Streamlit/gi,        ''],
          [/Streamlit/g,                   'AlphaBot FX'],
        ];
        for (const [re, rep] of map){
          if (re.test(html)){ html = html.replace(re, rep); changed = true; }
        }
        if (changed) node.innerHTML = html;
      });
    } catch(e){}
  }
  new MutationObserver(() => { rebrand(); ensureMenuFab(); }).observe(D.body, {subtree:true, childList:true, characterData:true});
  rebrand();
  setInterval(() => { rebrand(); ensureMenuFab(); }, 1500);
})();
</script>
"""


def inject_css() -> None:
    if CSS_FILE.exists():
        st.markdown(f"<style>{CSS_FILE.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    # Viewport meta (CSS/markdown is fine for non-script content)
    st.markdown(
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
        unsafe_allow_html=True,
    )
    # JS must go through components.html (markdown strips <script> tags)
    components.html(_JS_HELPERS, height=0, width=0)


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
