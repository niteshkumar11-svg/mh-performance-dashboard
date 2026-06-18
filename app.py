"""
BJOC - All In One Dashboard  ·  Streamlit
=========================================
Every tab in the Google Sheet is a *metric* named ``<Metric>-<Function>``
(function = FC or MH). Navigation:

    pick a Function (FC / MH)  ->  pick a Metric  ->  its table renders

Tables are reproduced faithfully (sheet colours, merged cells, frozen panes),
and only the selected tab's data is fetched (on demand) so it stays fast.

Run:  streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

import data_loader as dl

try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTOREFRESH = True
except Exception:  # noqa: BLE001
    _HAS_AUTOREFRESH = False

# --------------------------------------------------------------------------- #
# Page setup
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="BJOC - All In One Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

HDR_LABEL = "#a4c2f4"   # fallback header colour for cells with no fill

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
      :root { --accent:#1f6feb; --accent2:#4f46e5; --ink:#102a4a; --line:#dbe2ea; }
      html, body, [data-testid="stAppViewContainer"] {
          font-family:'Inter', system-ui, sans-serif; }

      /* full-width content, minimal top space */
      .block-container,
      [data-testid="stMainBlockContainer"],
      [data-testid="stAppViewBlockContainer"] {
          max-width:100% !important; padding:0.3rem 1.2rem 0.6rem !important; }
      header[data-testid="stHeader"] {
          height:2.2rem; background:transparent; backdrop-filter:none; }
      [data-testid="stSidebar"] { background:#f7f9fc; border-right:1px solid var(--line); }

      /* highlighted app banner */
      .app-banner { text-align:center; font-weight:800; font-size:1.6rem;
          letter-spacing:1.5px; color:#fff; padding:.65rem 1rem; border-radius:14px;
          margin:.1rem 0 .55rem;
          background:linear-gradient(135deg,#1f6feb 0%,#4f46e5 55%,#7c3aed 100%);
          box-shadow:0 4px 14px rgba(31,111,235,.28); }

      /* section labels + selected-metric title */
      .sec-label { font-weight:700; color:#64748b; font-size:.8rem;
          letter-spacing:.8px; text-transform:uppercase; margin:.2rem 0 .1rem; }
      .metric-title { text-align:center; font-weight:800; font-size:1.3rem;
          color:var(--ink); margin:.5rem 0 .3rem; animation:fadeInUp .4s ease both; }
      .metric-title .accent { display:block; width:60px; height:4px; border-radius:3px;
          margin:.3rem auto 0; background:linear-gradient(90deg,var(--accent),#7aa7ff); }
      .hint { text-align:center; color:#7b8794; padding:1.4rem; font-size:1.02rem;
          animation:fadeInUp .4s ease both; }

      /* animations */
      @keyframes fadeInUp { from{opacity:0; transform:translateY(10px);} to{opacity:1; transform:none;} }
      @keyframes popIn   { 0%{opacity:0; transform:scale(.96) translateY(8px);} 100%{opacity:1; transform:none;} }

      /* buttons (function + metric) */
      .stButton > button { border-radius:10px; font-weight:600; border:1px solid var(--line);
          padding:.45rem .6rem; transition:transform .12s, box-shadow .12s, background .12s;
          animation:popIn .35s ease both; }
      .stButton > button:hover { transform:translateY(-2px);
          box-shadow:0 6px 16px rgba(31,111,235,.18); }
      .stButton > button[kind="primary"] {
          background:linear-gradient(135deg,var(--accent),var(--accent2));
          border:0; color:#fff; box-shadow:0 3px 10px rgba(31,111,235,.28); }
      .stButton > button[kind="secondary"] { background:#fff; color:#1f2d3d; }
      /* stagger the buttons within a row for a cascading reveal */
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) .stButton>button{animation-delay:.02s}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) .stButton>button{animation-delay:.06s}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3) .stButton>button{animation-delay:.10s}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(4) .stButton>button{animation-delay:.14s}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(5) .stButton>button{animation-delay:.18s}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(6) .stButton>button{animation-delay:.22s}

      /* TABLE: taller (max vertical view); only the table scrolls. */
      .sheet-wrap { overflow:auto; max-height:calc(100vh - 12rem);
          border:1px solid var(--line); border-radius:10px;
          box-shadow:0 1px 4px rgba(16,42,74,.08); animation:fadeInUp .45s ease both; }
      table.sheet { border-collapse:separate; border-spacing:0; width:auto;
          min-width:max-content; font-size:var(--fs,0.9rem);
          font-family:'Inter', system-ui, sans-serif; }
      table.sheet th, table.sheet td {
          border:1px solid #d8dee6; padding:7px 12px; text-align:center;
          vertical-align:middle; white-space:nowrap; overflow-wrap:normal;
          min-width:var(--cw,6em); }
      table.sheet thead th { position:sticky; top:0; z-index:2; font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# HTML rendering (faithful: colours + merged cells + frozen panes)
# --------------------------------------------------------------------------- #
def _text_color(hexc: str) -> str:
    if not isinstance(hexc, str) or len(hexc) != 7 or not hexc.startswith("#"):
        return ""
    r, g, b = int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16)
    return "#ffffff" if (0.299 * r + 0.587 * g + 0.114 * b) < 140 else ""


def _bg_style(bg: str) -> str:
    if not isinstance(bg, str) or not bg:
        return ""
    tc = _text_color(bg)
    return f"background-color:{bg};" + (f"color:{tc};" if tc else "")


def _esc(s) -> str:
    s = "" if s is None else str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _frozen(pos: int, frozen_cols: int, is_header: bool, bg: str, w: float) -> str:
    """Sticky-left style for column `pos` of a frozen pane (width follows slider)."""
    if pos >= frozen_cols:
        return ""
    s = (f"position:sticky;left:{round(pos * w, 2)}em;"
         f"width:{w}em;min-width:{w}em;max-width:{w}em;"
         f"white-space:normal;overflow-wrap:anywhere;"
         f"z-index:{4 if is_header else 1};")
    if not bg:
        s += "background-color:#ffffff;"
    return s


def render_table(values, colors, frozen=(1, 1), merges=None,
                 font_rem: float = 0.9, cell_w: float = 6.0, label_w: float = 9.0) -> str:
    """Render an arbitrary sheet tab faithfully: header row sticky, first
    `frozen_cols` columns frozen-left, merged ranges, all borders, sheet colours."""
    grid = [list(r) for r in values]
    while grid and not any(str(c).strip() for c in grid[-1]):
        grid.pop()
    if not grid:
        return "<em>No data.</em>"
    nrows = len(grid)
    ncols = max(len(r) for r in grid)
    while ncols > 0 and all(len(r) < ncols or not str(r[ncols - 1]).strip() for r in grid):
        ncols -= 1
    if ncols == 0:
        return "<em>No data.</em>"

    def color_at(r, c):
        return colors[r][c] if (r < len(colors) and c < len(colors[r])) else ""

    fr, fc = frozen
    fc = min(fc, ncols)
    fr = max(1, fr)

    anchor, covered = {}, set()
    for sr, er, sc, ec in (merges or []):
        er, ec = min(er, nrows), min(ec, ncols)
        if sr >= nrows or sc >= ncols or er - sr < 1 or ec - sc < 1:
            continue
        if (er - sr) == 1 and (ec - sc) == 1:
            continue
        anchor[(sr, sc)] = (er - sr, ec - sc)
        for rr in range(sr, er):
            for cc in range(sc, ec):
                if (rr, cc) != (sr, sc):
                    covered.add((rr, cc))

    use_thead = not any(r == 0 and rs > 1 for (r, _), (rs, _) in anchor.items())

    def render_row(r: int, tag: str) -> str:
        cells = []
        for c in range(ncols):
            if (r, c) in covered:
                continue
            span = ""
            if (r, c) in anchor:
                rs, cs = anchor[(r, c)]
                if rs > 1:
                    span += f' rowspan="{rs}"'
                if cs > 1:
                    span += f' colspan="{cs}"'
            bg = color_at(r, c)
            if tag == "th" and not bg:
                bg = HDR_LABEL
            val = grid[r][c] if c < len(grid[r]) else ""
            style = _bg_style(bg) + _frozen(c, fc, tag == "th", bg, label_w)
            wt = "font-weight:700;" if (tag == "th" or r < fr) else ""
            cells.append(f'<{tag}{span} style="{style}{wt}">{_esc(val)}</{tag}>')
        return "<tr>" + "".join(cells) + "</tr>"

    html = [f'<div class="sheet-wrap"><table class="sheet" '
            f'style="--fs:{font_rem}rem;--cw:{cell_w}em">']
    if use_thead:
        html.append("<thead>" + render_row(0, "th") + "</thead><tbody>")
        start = 1
    else:
        html.append("<tbody>")
        start = 0
    for r in range(start, nrows):
        html.append(render_row(r, "td"))
    html.append("</tbody></table></div>")
    return "".join(html)


# --------------------------------------------------------------------------- #
# Data access (cached, on-demand per tab)
# --------------------------------------------------------------------------- #
def _has_sa() -> bool:
    try:
        return "gcp_service_account" in st.secrets
    except Exception:  # noqa: BLE001
        return False


@st.cache_data(ttl=900, show_spinner=False)
def get_meta(tick: int = 0) -> list:
    return dl.load_meta(dict(st.secrets["gcp_service_account"]))


@st.cache_data(ttl=900, show_spinner="Loading table…")
def get_grid(title: str, tick: int = 0):
    return dl.load_tab_grid(dict(st.secrets["gcp_service_account"]), title)


# --------------------------------------------------------------------------- #
# Sidebar — settings
# --------------------------------------------------------------------------- #
st.sidebar.markdown("##### ⚙️ Controls")

if not _has_sa():
    st.error("No service account configured. Add `gcp_service_account` to "
             "`.streamlit/secrets.toml` (see README).")
    st.stop()

_RF = {"Off": 0, "30 sec": 30, "1 min": 60, "5 min": 300}
rf_choice = st.sidebar.selectbox("⏱️ Auto-refresh", list(_RF), index=2)
rf_sec = _RF[rf_choice]
tick = 0
if rf_sec and _HAS_AUTOREFRESH:
    tick = st_autorefresh(interval=rf_sec * 1000, key="auto_rf")

st.sidebar.divider()
font_rem = st.sidebar.slider("🔠 Table font size", 0.6, 1.5, 0.9, 0.05)
cell_w = st.sidebar.slider("↔️ Data cell width", 2.5, 14.0, 6.0, 0.5,
                           help="Width of the metric/date data columns.")
label_w = st.sidebar.slider("🏷️ Label (frozen) width", 3.0, 22.0, 9.0, 0.5,
                            help="Width of the frozen left (label) columns.")

# --------------------------------------------------------------------------- #
# Load tab catalogue
# --------------------------------------------------------------------------- #
try:
    tabs = get_meta(tick=tick)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not read the sheet.\n\n```\n{exc}\n```")
    st.stop()
if not tabs:
    st.warning("No visible tabs found in the sheet.")
    st.stop()

present = [t["function"] for t in tabs if t["function"]]
functions = [f for f in ("FC", "MH") if f in present] + \
            [f for f in sorted(set(present)) if f not in ("FC", "MH")]

if "func" not in st.session_state or st.session_state.func not in functions:
    st.session_state.func = functions[0] if functions else None
st.session_state.setdefault("metric", None)

# --------------------------------------------------------------------------- #
# Banner + Refresh
# --------------------------------------------------------------------------- #
st.markdown("<div class='app-banner'>BJOC&nbsp;-&nbsp;ALL IN ONE DASHBOARD</div>",
            unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Function buttons (FC / MH)
# --------------------------------------------------------------------------- #
st.markdown("<div class='sec-label'>Function</div>", unsafe_allow_html=True)
fcols = st.columns(8)
for i, f in enumerate(functions):
    if fcols[i].button(f, key=f"fn_{f}", use_container_width=True,
                       type="primary" if st.session_state.func == f else "secondary"):
        st.session_state.func = f
        st.session_state.metric = None
        st.rerun()
# Refresh sits at the far right of the function row
if fcols[7].button("🔄", key="refresh_btn", use_container_width=True,
                   help="Refresh data now"):
    get_meta.clear()
    get_grid.clear()
    st.rerun()

# --------------------------------------------------------------------------- #
# Metric buttons for the chosen function
# --------------------------------------------------------------------------- #
metrics = [t for t in tabs if t["function"] == st.session_state.func]
st.markdown(f"<div class='sec-label'>{st.session_state.func} metrics</div>",
            unsafe_allow_html=True)

PER_ROW = 6
for start in range(0, len(metrics), PER_ROW):
    row = metrics[start:start + PER_ROW]
    cols = st.columns(PER_ROW)
    for j, t in enumerate(row):
        active = st.session_state.metric == t["title"]
        if cols[j].button(t["metric"], key=f"m_{t['title']}", use_container_width=True,
                          type="primary" if active else "secondary"):
            st.session_state.metric = t["title"]
            st.rerun()

# --------------------------------------------------------------------------- #
# Selected metric table
# --------------------------------------------------------------------------- #
sel = st.session_state.metric
if not sel or sel not in {t["title"] for t in metrics}:
    st.markdown("<div class='hint'>👆 Pick a metric above to view its table.</div>",
                unsafe_allow_html=True)
    st.stop()

tab = next(t for t in tabs if t["title"] == sel)
st.markdown(f"<div class='metric-title'>{_esc(tab['metric'])} "
            f"<span style='color:#94a3b8;font-weight:600;font-size:.95rem'>· {tab['function']}</span>"
            f"<span class='accent'></span></div>", unsafe_allow_html=True)

try:
    values, colors, truncated = get_grid(sel, tick=tick)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load **{sel}**.\n\n```\n{exc}\n```")
    st.stop()

st.markdown(
    render_table(values, colors, frozen=tab["frozen"], merges=tab["merges"],
                 font_rem=font_rem, cell_w=cell_w, label_w=label_w),
    unsafe_allow_html=True,
)
if truncated:
    st.caption("⚠️ Large tab — showing the first portion of rows/columns.")

csv = "\n".join(
    ",".join('"' + str(c).replace('"', '""') + '"' for c in row)
    for row in values if any(str(c).strip() for c in row)
).encode("utf-8")
st.download_button("⬇️ Download (CSV)", csv, f"{sel}.csv", "text/csv")
