"""
BJOC - All In One Dashboard  ·  Streamlit
=========================================
Each tab in the Google Sheet is a metric named ``<Metric>-<Function>``
(function = FC, MH, or anything you add). Staged navigation:

    1. Two big buttons (FC / MH ...) — nothing selected by default.
    2. Click one  -> it shrinks, the function's metric buttons animate in.
    3. Click a metric -> buttons shrink small, the table animates in.

Date-based tables also get Overall / Week / Month views (latest date first).
Tables reproduce the sheet faithfully (colours, merges) and use the sheet's
own freeze settings (nothing is frozen by default). New tabs/functions added
to the sheet appear automatically (live read + auto-refresh) — no code change.

Run:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
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

HDR_LABEL = "#a4c2f4"

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
      :root { --accent:#1f6feb; --accent2:#4f46e5; --ink:#102a4a; --line:#dbe2ea; }
      html, body, [data-testid="stAppViewContainer"] { font-family:'Inter', system-ui, sans-serif; }

      .block-container,[data-testid="stMainBlockContainer"],[data-testid="stAppViewBlockContainer"]{
          max-width:100% !important; padding:0 1.2rem 0.5rem !important; }
      header[data-testid="stHeader"]{ height:1.4rem; background:transparent; backdrop-filter:none; }
      [data-testid="stDecoration"]{ display:none; }   /* thin rainbow bar at the very top */
      [data-testid="stSidebar"]{ background:#f7f9fc; border-right:1px solid var(--line); }

      .app-banner{ text-align:center; font-weight:800; font-size:1.55rem; letter-spacing:1.5px;
          color:#fff; padding:.6rem 1rem; border-radius:14px; margin:-0.3rem 0 .5rem;
          background:linear-gradient(135deg,#232323 0%,#000000 100%);
          box-shadow:0 4px 14px rgba(0,0,0,.32); }
      .sec-label{ font-weight:700; color:#64748b; font-size:.75rem; letter-spacing:.8px;
          text-transform:uppercase; margin:.35rem 0 .15rem; }
      .metric-title{ text-align:center; font-weight:800; font-size:1.15rem; color:var(--ink);
          margin:.3rem 0 .2rem; animation:fadeInUp .4s ease both; }
      .metric-title .accent{ display:block; width:54px; height:3px; border-radius:3px;
          margin:.25rem auto 0; background:linear-gradient(90deg,var(--accent),#7aa7ff); }
      .hint{ text-align:center; color:#7b8794; padding:1.2rem; font-size:1.05rem;
          animation:fadeInUp .4s ease both; }

      @keyframes fadeInUp{ from{opacity:0; transform:translateY(10px);} to{opacity:1; transform:none;} }
      @keyframes popIn{ 0%{opacity:0; transform:scale(.95) translateY(10px);} 100%{opacity:1; transform:none;} }

      /* pill buttons: white default, solid-blue when selected, blue-outline on hover */
      .stButton > button{ border-radius:11px; font-weight:600; border:1.5px solid #cbd5e1;
          background:#fff; color:#1f2d3d; box-shadow:0 1px 3px rgba(16,42,74,.10);
          transition:all .15s ease; animation:popIn .35s ease both; }
      .stButton > button:hover{ border-color:var(--accent); color:var(--accent);
          background:#fff; transform:translateY(-2px); box-shadow:0 6px 16px rgba(31,111,235,.20); }
      .stButton > button[kind="primary"]{ background:var(--accent); border:1.5px solid var(--accent);
          color:#fff; box-shadow:0 4px 12px rgba(31,111,235,.32); }
      .stButton > button[kind="primary"]:hover{ background:var(--accent2);
          border-color:var(--accent2); color:#fff; }
      .stButton > button[kind="secondary"]{ background:#fff; color:#1f2d3d; }
      /* cascade metric buttons within a row */
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) .stButton>button{animation-delay:.02s}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) .stButton>button{animation-delay:.06s}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3) .stButton>button{animation-delay:.10s}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(4) .stButton>button{animation-delay:.14s}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(5) .stButton>button{animation-delay:.18s}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(6) .stButton>button{animation-delay:.22s}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(7) .stButton>button{animation-delay:.26s}
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(8) .stButton>button{animation-delay:.30s}

      .sheet-wrap{ overflow:auto; max-height:calc(100vh - 11rem); border:1px solid var(--line);
          border-radius:10px; box-shadow:0 1px 4px rgba(16,42,74,.08); animation:fadeInUp .45s ease both; }
      table.sheet{ border-collapse:separate; border-spacing:0; width:auto; min-width:max-content;
          font-size:var(--fs,0.9rem); font-family:'Inter', system-ui, sans-serif; }
      table.sheet th, table.sheet td{ border:1px solid #d8dee6; padding:7px 12px; text-align:center;
          vertical-align:middle; white-space:nowrap; overflow-wrap:normal; min-width:var(--cw,6em); }
      table.sheet thead th{ position:sticky; top:0; z-index:2; font-weight:700; }
    </style>
    """,
    unsafe_allow_html=True,
)


def stage_css(stage: int) -> None:
    """Inject sizing for the current stage (1=big functions, 2=metrics, 3=table)."""
    # function buttons are circles in every stage; big in stage 1, small after
    css = '[class*="st-key-fn_"]{ display:flex; justify-content:center; }'
    if stage == 1:
        css += """
          [class*="st-key-fn_"] button{ width:24vh; height:24vh; border-radius:50%; padding:0;
              font-size:2rem; font-weight:800; letter-spacing:1px; color:#fff !important;
              border:1.5px solid var(--accent) !important; background:var(--accent) !important;
              box-shadow:0 10px 30px rgba(31,111,235,.30); animation:popIn .5s ease both; }
          [class*="st-key-fn_"] button:hover{ background:var(--accent2) !important;
              border-color:var(--accent2) !important; color:#fff !important; }
        """
    else:
        css += '[class*="st-key-fn_"] button{ width:3.6rem; height:3.6rem; border-radius:50%;' \
               ' padding:0; font-size:.82rem; }'
        if stage == 3:
            css += (
                '[class*="st-key-mt_"] button{ min-height:1.9rem; font-size:.78rem; padding:.2rem .4rem; }'
                '.sheet-wrap{ max-height:calc(100vh - 8rem) !important; }'
            )
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Rendering helpers
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
    if pos >= frozen_cols:
        return ""
    s = (f"position:sticky;left:{round(pos * w, 2)}em;width:{w}em;min-width:{w}em;max-width:{w}em;"
         f"white-space:normal;overflow-wrap:anywhere;z-index:{4 if is_header else 1};")
    if not bg:
        s += "background-color:#ffffff;"
    return s


# tried in order; day-first numeric forms before month-first so e.g. 27-03-2026
# reads as 27-Mar, while 04-13-2026 (invalid as day-first) falls through to month-first.
_DATE_FMTS = ("%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d",
              "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%y", "%d %b %Y", "%d %B %Y")


def _to_date(s):
    s = str(s).strip()
    if not s or len(s) < 6:
        return None
    for fmt in _DATE_FMTS:
        try:
            d = pd.to_datetime(s, format=fmt)
            return None if pd.isna(d) else d
        except (ValueError, TypeError):
            continue
    return None


def find_date_cols(header_row, start: int):
    out = []
    for c in range(start, len(header_row)):
        d = _to_date(header_row[c])
        if d is not None:
            out.append((c, d))
    return out


def find_date_rows(values, start_row: int, col: int = 0):
    out = []
    for r in range(start_row, len(values)):
        cell = values[r][col] if col < len(values[r]) else ""
        d = _to_date(cell)
        if d is not None:
            out.append((r, d))
    return out


def slice_rows(values, colors, merges, keep_rows):
    """Keep only `keep_rows` (in given order); remap merges that stay contiguous."""
    rowmap = {r: i for i, r in enumerate(keep_rows)}
    keepset = set(keep_rows)
    nv = [values[r] for r in keep_rows]
    nc = [(colors[r] if r < len(colors) else []) for r in keep_rows]
    nm = []
    for sr, er, sc, ec in (merges or []):
        rows = list(range(sr, er))
        if rows and all(rr in keepset for rr in rows):
            nw = [rowmap[rr] for rr in rows]
            if nw == list(range(min(nw), max(nw) + 1)):
                nm.append((min(nw), max(nw) + 1, sc, ec))
    return nv, nc, nm


def slice_cols(values, colors, merges, keep_cols):
    """Keep only `keep_cols` (in given order); remap merges that stay contiguous."""
    colmap = {c: i for i, c in enumerate(keep_cols)}
    keepset = set(keep_cols)
    nv = [[(row[c] if c < len(row) else "") for c in keep_cols] for row in values]
    nc = [[(colors[r][c] if r < len(colors) and c < len(colors[r]) else "")
           for c in keep_cols] for r in range(len(values))]
    nm = []
    for sr, er, sc, ec in (merges or []):
        cols = list(range(sc, ec))
        if cols and all(c in keepset for c in cols):
            nw = [colmap[c] for c in cols]
            if nw == list(range(min(nw), max(nw) + 1)):
                nm.append((sr, er, min(nw), max(nw) + 1))
    return nv, nc, nm


def render_table(values, colors, frozen=(0, 0), merges=None,
                 font_rem: float = 0.9, cell_w: float = 6.0, label_w: float = 9.0) -> str:
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
    fc = max(0, min(fc, ncols))
    fr = max(0, fr)

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

    # sticky header only if the sheet freezes >=1 row and no merge crosses row 0
    use_thead = fr >= 1 and not any(r == 0 and rs > 1 for (r, _), (rs, _) in anchor.items())

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
# Data access (cached, on-demand)
# --------------------------------------------------------------------------- #
def _has_sa() -> bool:
    try:
        return "gcp_service_account" in st.secrets
    except Exception:  # noqa: BLE001
        return False


@st.cache_data(ttl=300, show_spinner=False)
def get_meta(tick: int = 0) -> list:
    return dl.load_meta(dict(st.secrets["gcp_service_account"]))


@st.cache_data(ttl=300, show_spinner="Loading table…")
def get_grid(title: str, ncols: int = 60, nrows: int = 60, tick: int = 0):
    # fetch wide enough to reach the latest dates (rightmost cols), bounded by a
    # total-cell budget so high-row tabs don't blow up the payload
    mc = min(max(int(ncols), 60), 600)
    mr = min(max(int(nrows), 40), 400)
    if mr * mc > 150_000:
        mc = max(60, 150_000 // mr)
    return dl.load_tab_grid(dict(st.secrets["gcp_service_account"]), title,
                            max_rows=mr, max_cols=mc)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
st.sidebar.markdown("##### ⚙️ Controls")
if not _has_sa():
    st.error("No service account configured. Add `gcp_service_account` to "
             "`.streamlit/secrets.toml` (see README).")
    st.stop()

if st.sidebar.button("🔄 Refresh now", key="refresh_btn", use_container_width=True):
    get_meta.clear()
    get_grid.clear()
    st.rerun()

_RF = {"Off": 0, "30 sec": 30, "1 min": 60, "5 min": 300}
rf_choice = st.sidebar.selectbox("⏱️ Auto-refresh", list(_RF), index=2)
rf_sec = _RF[rf_choice]
tick = 0
if rf_sec and _HAS_AUTOREFRESH:
    tick = st_autorefresh(interval=rf_sec * 1000, key="auto_rf")

st.sidebar.divider()
font_rem = st.sidebar.slider("🔠 Table font size", 0.6, 1.5, 0.9, 0.05)
cell_w = st.sidebar.slider("↔️ Data cell width", 2.5, 14.0, 6.0, 0.5)
label_w = st.sidebar.slider("🏷️ Label (frozen) width", 3.0, 22.0, 9.0, 0.5)

# --------------------------------------------------------------------------- #
# Catalogue
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

st.session_state.setdefault("func", None)          # nothing selected by default
st.session_state.setdefault("metric", None)
if st.session_state.func not in functions:
    st.session_state.func = None
    st.session_state.metric = None

stage = 1 if st.session_state.func is None else (3 if st.session_state.metric else 2)
stage_css(stage)

# --------------------------------------------------------------------------- #
# Banner
# --------------------------------------------------------------------------- #
st.markdown("<div class='app-banner'>BJOC&nbsp;-&nbsp;ALL IN ONE DASHBOARD</div>",
            unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Function buttons (big in stage 1, small after)
# --------------------------------------------------------------------------- #
if stage == 1:
    fcols = st.columns(len(functions) or 1)
else:
    fcols = st.columns([1, 1] + [6])           # two small buttons, rest empty
for i, f in enumerate(functions):
    if fcols[i].button(f, key=f"fn_{f}", use_container_width=False,
                       type="primary" if st.session_state.func == f else "secondary"):
        st.session_state.func = f
        st.session_state.metric = None
        st.rerun()

if stage == 1:
    st.markdown("<div class='hint'>👆 Select a function to begin.</div>",
                unsafe_allow_html=True)
    st.stop()

# --------------------------------------------------------------------------- #
# Metric buttons for the chosen function
# --------------------------------------------------------------------------- #
metrics = [t for t in tabs if t["function"] == st.session_state.func]
st.markdown(f"<div class='sec-label'>{st.session_state.func} metrics</div>",
            unsafe_allow_html=True)
per_row = 8 if stage == 3 else 6
for start in range(0, len(metrics), per_row):
    row = metrics[start:start + per_row]
    cols = st.columns(per_row)
    for j, t in enumerate(row):
        active = st.session_state.metric == t["title"]
        if cols[j].button(t["metric"], key=f"mt_{t['title']}", use_container_width=True,
                          type="primary" if active else "secondary"):
            st.session_state.metric = t["title"]
            st.rerun()

sel = st.session_state.metric
if not sel or sel not in {t["title"] for t in metrics}:
    st.markdown("<div class='hint'>👆 Pick a metric to view its table.</div>",
                unsafe_allow_html=True)
    st.stop()

# --------------------------------------------------------------------------- #
# Selected metric table (with Overall / Week / Month for dated tables)
# --------------------------------------------------------------------------- #
tab = next(t for t in tabs if t["title"] == sel)
st.markdown(f"<div class='metric-title'>{_esc(tab['metric'])} "
            f"<span style='color:#94a3b8;font-weight:600;font-size:.9rem'>· {tab['function']}</span>"
            f"<span class='accent'></span></div>", unsafe_allow_html=True)

try:
    values, colors, truncated = get_grid(sel, ncols=tab["cols"], nrows=tab["rows"], tick=tick)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load **{sel}**.\n\n```\n{exc}\n```")
    st.stop()

fr, fc = tab["frozen"]
merges = tab["merges"]
hdr_rows = max(1, fr)


def _iso(d):
    return (int(d.isocalendar().year), int(d.isocalendar().week))


def detect_date_header(grid, max_search=6):
    """Find the row that holds the dates (search the first few rows). Returns
    (row_index, [(col, date), ...] sorted by col). Handles multi-row headers."""
    best_row, best = None, []
    for r in range(min(max_search, len(grid))):
        starts = [(c, _to_date(grid[r][c])) for c in range(len(grid[r])) if _to_date(grid[r][c])]
        if len(starts) > len(best):
            best, best_row = starts, r
    return best_row, sorted(best, key=lambda x: x[0])


def date_groups_from(date_starts, ncols_full):
    """Each date owns the columns from its start up to the next date's start
    (so a date that visually spans several sub-columns keeps them all)."""
    gmap = {}
    for i, (c, d) in enumerate(date_starts):
        end = date_starts[i + 1][0] if i + 1 < len(date_starts) else ncols_full
        gmap.setdefault(d, []).extend(range(c, end))
    return gmap


# horizontal dates (a header row anywhere in the first rows) — generic
dr_row, date_starts = detect_date_header(values)
# vertical dates (down the first column) — only if not a header-date table
date_rows = []
if len(date_starts) < 4:
    cand = find_date_rows(values, hdr_rows, 0)
    if len(cand) >= 4 and cand[0][0] <= hdr_rows + 1:
        date_rows = cand


def show_cols(keep_cols, frozen):
    v, c, m = slice_cols(values, colors, merges, keep_cols)
    st.markdown(render_table(v, c, frozen=frozen, merges=m,
                             font_rem=font_rem, cell_w=cell_w, label_w=label_w),
                unsafe_allow_html=True)


def show_rows(keep_rows):
    v, c, m = slice_rows(values, colors, merges, keep_rows)
    st.markdown(render_table(v, c, frozen=(fr, fc), merges=m,
                             font_rem=font_rem, cell_w=cell_w, label_w=label_w),
                unsafe_allow_html=True)


if len(date_starts) >= 4:
    # ---- dates across a header row: slice COLUMNS by date group (latest first) ----
    ncols_full = max(len(r) for r in values)
    first_date_col = date_starts[0][0]
    labels = list(range(first_date_col))            # everything before the first date
    gmap = date_groups_from(date_starts, ncols_full)
    dates_desc = sorted(gmap.keys(), reverse=True)
    frz = (fr, first_date_col)                       # freeze header rows + label cols
    t_over, t_week, t_month = st.tabs(["Overall (last 4 days)", "Week", "Month"])
    with t_over:
        cols = labels + [c for d in dates_desc[:4] for c in gmap[d]]
        show_cols(cols, frz)
    with t_week:
        weeks = sorted({_iso(d) for d in gmap}, reverse=True)
        wk = st.selectbox("Week", weeks, key="wk_sel", format_func=lambda k: f"Week {k[1]}, {k[0]}")
        cols = labels + [c for d in dates_desc if _iso(d) == wk for c in gmap[d]]
        show_cols(cols, frz)
    with t_month:
        months = sorted({(d.year, d.month) for d in gmap}, reverse=True)
        mo = st.selectbox("Month", months, key="mo_sel",
                          format_func=lambda k: pd.Timestamp(year=k[0], month=k[1], day=1).strftime("%B %Y"))
        cols = labels + [c for d in dates_desc if (d.year, d.month) == mo for c in gmap[d]]
        show_cols(cols, frz)
elif date_rows:
    # ---- dates down the first column: slice ROWS (latest first) ----
    head = list(range(hdr_rows))
    desc = sorted(date_rows, key=lambda x: x[1], reverse=True)
    t_over, t_week, t_month = st.tabs(["Overall (last 4 days)", "Week", "Month"])
    with t_over:
        show_rows(head + [r for r, _ in desc[:4]])
    with t_week:
        weeks = sorted({_iso(d) for _, d in date_rows}, reverse=True)
        wk = st.selectbox("Week", weeks, key="wk_sel_r", format_func=lambda k: f"Week {k[1]}, {k[0]}")
        show_rows(head + [r for r, d in desc if _iso(d) == wk])
    with t_month:
        months = sorted({(d.year, d.month) for _, d in date_rows}, reverse=True)
        mo = st.selectbox("Month", months, key="mo_sel_r",
                          format_func=lambda k: pd.Timestamp(year=k[0], month=k[1], day=1).strftime("%B %Y"))
        show_rows(head + [r for r, d in desc if (d.year, d.month) == mo])
else:
    st.markdown(render_table(values, colors, frozen=(fr, fc), merges=merges,
                             font_rem=font_rem, cell_w=cell_w, label_w=label_w),
                unsafe_allow_html=True)

if truncated:
    st.caption("⚠️ Large tab — showing the first portion of rows/columns.")

csv = "\n".join(
    ",".join('"' + str(c).replace('"', '""') + '"' for c in row)
    for row in values if any(str(c).strip() for c in row)
).encode("utf-8")
st.download_button("⬇️ Download (CSV)", csv, f"{sel}.csv", "text/csv")
