"""
Ops KPI Dashboard  ·  Streamlit
================================
Day-on-day view of the daily Charter/Metrics sheet, rendered to match the
Google Sheet itself: metrics as rows (in sheet order), dates as columns,
Charter cells merged (rowspan), and each cell painted with the sheet's own
background colour / conditional formatting.

Four time views:
  • 🗂️ Overall – the most recent N days (default 7) side by side.
  • 📅 Day     – pick a date -> all metrics for that day (+ day-on-day change).
  • 🗓️ Week    – pick a week number -> date-wise data for every day that week.
  • 📆 Month   – pick a month -> date-wise data for every day that month.

Only worksheet tabs that are *visible* (not hidden) in the sheet are shown.

Run:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import data_loader as dl

try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTOREFRESH = True
except Exception:  # noqa: BLE001 — graceful if the package isn't installed
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

# Header palette taken from the sheet (consistent across the DOD tabs)
HDR_LABEL = "#a4c2f4"   # Charter / Metric header (blue)
HDR_TARGET = "#93c47d"  # Target header (green)
HDR_DATE = "#20124d"    # date headers (dark navy, white text)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
      :root { --accent:#1f6feb; --accent-dark:#1a5fd0; --ink:#102a4a;
              --line:#dbe2ea; --panel:#ffffff; }
      html, body, [data-testid="stAppViewContainer"] {
          font-family:'Inter', system-ui, sans-serif; }

      /* full-width content with minimal space at the very top */
      .block-container,
      [data-testid="stMainBlockContainer"],
      [data-testid="stAppViewBlockContainer"] {
          max-width:100% !important; padding:0.35rem 1.4rem 0.8rem !important; }
      /* slim, transparent header so the sidebar toggle stays available */
      header[data-testid="stHeader"] {
          height:2.2rem; background:transparent; backdrop-filter:none; }

      /* highlighted app banner at the top of the main page */
      .app-banner { text-align:center; font-weight:800; font-size:1.7rem;
          letter-spacing:1.5px; color:#fff; padding:.75rem 1rem; border-radius:14px;
          margin:.1rem 0 .7rem;
          background:linear-gradient(135deg,#1f6feb 0%,#4f46e5 55%,#7c3aed 100%);
          box-shadow:0 4px 14px rgba(31,111,235,.28); }

      /* centered hub title with a small accent underline (not sticky -> no overlap) */
      .hub-title { text-align:center; font-weight:800; font-size:1.45rem;
          color:var(--ink); letter-spacing:.3px; margin:.1rem 0 .2rem; }
      .hub-title .accent { display:block; width:64px; height:4px; border-radius:3px;
          margin:.3rem auto 0; background:linear-gradient(90deg,var(--accent),#7aa7ff); }

      /* tabs */
      [data-baseweb="tab-list"] { gap:.35rem; border-bottom:1px solid var(--line); }
      [data-baseweb="tab"] { font-weight:600; color:#5b6b7d; }
      [data-baseweb="tab"][aria-selected="true"] { color:var(--accent); }
      [data-baseweb="tab-highlight"] { background:var(--accent) !important; height:3px; }

      /* buttons */
      .stButton > button { background:var(--accent); color:#fff; border:0;
          border-radius:8px; font-weight:600; transition:.15s; }
      .stButton > button:hover { background:var(--accent-dark); color:#fff; }

      /* sidebar */
      [data-testid="stSidebar"] { background:#f7f9fc; border-right:1px solid var(--line); }

      /* Only the TABLE scrolls (fills the page), so the title/tabs above never
         scroll away and never overlap the data. */
      .sheet-wrap { overflow:auto; max-height:calc(100vh - 12.5rem);
          border:1px solid var(--line); border-radius:10px;
          box-shadow:0 1px 4px rgba(16,42,74,.08); }
      table.sheet { border-collapse:separate; border-spacing:0; width:auto;
          font-size:var(--fs,0.9rem); font-family:'Inter', system-ui, sans-serif; }
      table.sheet.fit  { width:100%; }              /* metrics table: fill the page */
      table.sheet.wide { min-width:max-content; }    /* raw sheets: size to content */
      /* all borders, text wraps */
      table.sheet th, table.sheet td {
          border:1px solid #d8dee6; padding:7px 12px;
          text-align:center; vertical-align:middle;
          white-space:normal; overflow-wrap:anywhere; }
      table.sheet.wide th, table.sheet.wide td {
          white-space:nowrap; overflow-wrap:normal; min-width:var(--cw,6em); }
      table.sheet thead th { position:sticky; top:0; z-index:2; font-weight:700; }
      table.sheet td.metric { font-weight:600; }
      table.sheet td.charter { font-weight:700; color:#1e3a8a; }
      table.sheet td.num, table.sheet thead th.num {
          font-variant-numeric:tabular-nums;
          min-width:var(--cw,3.2em); width:var(--cw,3.2em); }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Data access (cached)
# --------------------------------------------------------------------------- #
@st.cache_data(ttl=900, show_spinner="Loading data…")
def get_data(source: str, tick: int = 0) -> tuple:
    # `tick` is part of the cache key: when the auto-refresh timer increments it,
    # the cache misses and data is re-fetched live from the sheet.
    if source == "Live (Google Sheets)":
        sa = dict(st.secrets["gcp_service_account"])
        return dl.load_live(sa)              # hidden tabs skipped inside loader
    return dl.load_snapshot()


def _has_service_account() -> bool:
    try:
        return "gcp_service_account" in st.secrets
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------- #
# HTML rendering helpers (merged cells + sheet colours)
# --------------------------------------------------------------------------- #
def _text_color(hexc: str) -> str:
    """Pick black/white text for legibility on a coloured background."""
    if not isinstance(hexc, str) or len(hexc) != 7 or not hexc.startswith("#"):
        return ""
    r, g, b = int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16)
    return "#ffffff" if (0.299 * r + 0.587 * g + 0.114 * b) < 140 else ""


def _bg_style(bg: str) -> str:
    if not isinstance(bg, str) or not bg:
        return ""
    out = f"background-color:{bg};"
    tc = _text_color(bg)
    return out + (f"color:{tc};" if tc else "")


def _esc(s) -> str:
    s = "" if s is None or (isinstance(s, float) and pd.isna(s)) else str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# em-widths of the frozen label columns (Charter, Metric, Target). em units
# scale with the table font-size, so the sticky offsets stay correct when the
# font slider changes.
_FROZEN_W = [7.0, 18.0, 5.0]         # relative ratios for Charter / Metric / Target


def _frozen_style(pos: int, frozen_cols: int, is_header: bool, bg: str,
                  scale: float = 1.0) -> str:
    """Sticky-left style for label column `pos` (0=Charter,1=Metric,2=Target).
    Widths (and the cumulative left offset) scale with the cell-width slider."""
    if pos >= min(frozen_cols, 3):
        return ""
    left = round(sum(_FROZEN_W[:pos]) * scale, 2)
    w = round(_FROZEN_W[pos] * scale, 2)
    s = (f"position:sticky;left:{left}em;"
         f"min-width:{w}em;max-width:{w}em;"
         f"z-index:{4 if is_header else 1};")
    if not bg:                       # opaque so scrolled cells don't show through
        s += "background-color:#ffffff;"
    return s


def render_sheet(frame: pd.DataFrame, dates, delta_map: dict | None = None,
                 frozen_cols: int = 3, font_rem: float = 0.85,
                 cell_w: float = 3.5, label_w: float = 9.0) -> str:
    """Build a sheet-faithful HTML table: merged Charter column, cell colours,
    frozen header row + frozen label columns, scalable font.

    `delta_map` (Day view): {Order: (text, bg)} adds a trailing change column.
    """
    # latest date first, then older dates (matches the sheet's column order)
    dates = sorted(pd.to_datetime(list(dates)), reverse=True)
    labels = [d.strftime("%d-%b") for d in dates]

    groups = [g for _, g in sorted(frame.groupby("Order"), key=lambda kv: kv[0])]
    if not groups:
        return "<em>No data.</em>"

    # row records in sheet order
    recs = []
    for g in groups:
        g0 = g.iloc[0]
        dmap = {r["Date"]: (r["Value_raw"], r["BgColor"]) for _, r in g.iterrows()}
        recs.append({
            "order": int(g0["Order"]),
            "charter": g0["Charter"], "charter_bg": g0.get("CharterBg", ""),
            "metric": g0["Metric"], "metric_bg": g0.get("MetricBg", ""),
            "target": g0["Target_raw"], "target_bg": g0.get("TargetBg", ""),
            "cells": [dmap.get(d, ("", "")) for d in dates],
        })

    # contiguous Charter run lengths -> rowspan
    spans = {}  # index -> span (only set on the first row of a run)
    i = 0
    while i < len(recs):
        j = i
        while j + 1 < len(recs) and recs[j + 1]["charter"] == recs[i]["charter"]:
            j += 1
        spans[i] = j - i + 1
        i = j + 1

    # frozen label-column widths are driven by their OWN slider (label_w sets the
    # Metric column; Charter/Target follow the fixed ratios) — independent of the
    # data-cell width, so the data columns stay the visible/highlighted ones.
    scale = label_w / _FROZEN_W[1]

    # --- header (frozen row; first `frozen_cols` label cols also frozen-left) ---
    html = [f'<div class="sheet-wrap"><table class="sheet fit" '
            f'style="--fs:{font_rem}rem;--cw:{cell_w}em">' '<thead><tr>']
    html.append(f'<th style="{_bg_style(HDR_LABEL)}'
                f'{_frozen_style(0, frozen_cols, True, HDR_LABEL, scale)}">Charter</th>')
    html.append(f'<th style="{_bg_style(HDR_LABEL)}'
                f'{_frozen_style(1, frozen_cols, True, HDR_LABEL, scale)}">Metric</th>')
    html.append(f'<th style="{_bg_style(HDR_TARGET)}'
                f'{_frozen_style(2, frozen_cols, True, HDR_TARGET, scale)}">Target</th>')
    for lab in labels:
        html.append(f'<th class="num" style="{_bg_style(HDR_DATE)}">{_esc(lab)}</th>')
    if delta_map is not None:
        html.append(f'<th class="num" style="{_bg_style(HDR_TARGET)}">Δ vs prev day</th>')
    html.append("</tr></thead><tbody>")

    # --- body ---
    for idx, rec in enumerate(recs):
        html.append("<tr>")
        if idx in spans:
            html.append(
                f'<td class="charter" rowspan="{spans[idx]}" '
                f'style="{_bg_style(rec["charter_bg"])}'
                f'{_frozen_style(0, frozen_cols, False, rec["charter_bg"], scale)}">'
                f'{_esc(rec["charter"])}</td>'
            )
        html.append(f'<td class="metric" style="{_bg_style(rec["metric_bg"])}'
                    f'{_frozen_style(1, frozen_cols, False, rec["metric_bg"], scale)}">'
                    f'{_esc(rec["metric"])}</td>')
        html.append(f'<td class="num" style="{_bg_style(rec["target_bg"])}'
                    f'{_frozen_style(2, frozen_cols, False, rec["target_bg"], scale)}">'
                    f'{_esc(rec["target"])}</td>')
        for val, bg in rec["cells"]:
            html.append(f'<td class="num" style="{_bg_style(bg)}">{_esc(val)}</td>')
        if delta_map is not None:
            txt, bg = delta_map.get(rec["order"], ("", ""))
            html.append(f'<td class="num" style="{_bg_style(bg)}">{_esc(txt)}</td>')
        html.append("</tr>")

    html.append("</tbody></table></div>")
    return "".join(html)


def _frozen_raw(pos: int, frozen_cols: int, is_header: bool, bg: str,
                w: float = 9.0) -> str:
    """Sticky-left style for column `pos` of a generic raw sheet. Column width
    `w` (and the cumulative left offset) follows the cell-width slider."""
    if pos >= frozen_cols:
        return ""
    s = (f"position:sticky;left:{pos * w}em;min-width:{w}em;max-width:{w}em;"
         f"white-space:normal;overflow-wrap:anywhere;"
         f"z-index:{4 if is_header else 1};")
    if not bg:
        s += "background-color:#ffffff;"
    return s


def render_raw(values, colors, frozen=(1, 1), font_rem: float = 0.9,
               cell_w: float = 7.0, merges=None, label_w: float = 9.0) -> str:
    """Render an arbitrary sheet (values + cell colours + merged cells)
    faithfully: header row sticky, first `frozen_cols` columns frozen-left,
    all borders, and merged ranges reproduced with colspan/rowspan."""
    grid = [list(r) for r in values]
    # trim trailing empty rows / columns
    while grid and not any(str(c).strip() for c in grid[-1]):
        grid.pop()
    if not grid:
        return "<em>No data.</em>"
    nrows = len(grid)
    ncols = max(len(r) for r in grid)
    while ncols > 0 and all(len(r) < ncols or not str(r[ncols - 1]).strip()
                            for r in grid):
        ncols -= 1
    if ncols == 0:
        return "<em>No data.</em>"

    def color_at(r, c):
        return colors[r][c] if (r < len(colors) and c < len(colors[r])) else ""

    fr, fc = frozen
    fc = min(fc, ncols)
    fr = max(1, fr)

    # build merge anchors (top-left cell -> span) and the set of covered cells
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

    # a thead can't hold a rowspan that crosses into the body
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
            style = _bg_style(bg) + _frozen_raw(c, fc, tag == "th", bg, label_w)
            wt = "font-weight:700;" if (tag == "th" or r < fr) else ""
            cells.append(f'<{tag}{span} style="{style}{wt}">{_esc(val)}</{tag}>')
        return "<tr>" + "".join(cells) + "</tr>"

    html = [f'<div class="sheet-wrap"><table class="sheet wide" '
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
# Sidebar — source, hub, charter filter
# --------------------------------------------------------------------------- #
st.sidebar.markdown("##### ⚙️ Controls")

has_secrets = _has_service_account()
source_options = []
if has_secrets:
    source_options.append("Live (Google Sheets)")
if dl.SNAPSHOT_PATH.exists():
    source_options.append("Snapshot (bundled CSV)")
if not source_options:
    st.error("No data source available. Configure a service account (live mode) "
             "or provide data/snapshot.csv.")
    st.stop()
source = st.sidebar.radio("Data source", source_options, index=0)
if not has_secrets:
    st.sidebar.caption("💡 Add a service account to enable live mode (see README).")

# Auto-refresh: soft rerun on a timer (must run before get_data so `tick` is set)
_RF = {"Off": 0, "30 sec": 30, "1 min": 60, "5 min": 300}
rf_choice = st.sidebar.selectbox("⏱️ Auto-refresh", list(_RF), index=2)
rf_sec = _RF[rf_choice]
tick = 0
if rf_sec and _HAS_AUTOREFRESH:
    tick = st_autorefresh(interval=rf_sec * 1000, key="auto_rf")
elif rf_sec:
    st.sidebar.caption("⚠️ `streamlit-autorefresh` not installed — using manual refresh.")

try:
    data, raw_sheets = get_data(source, tick=tick)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load data from **{source}**.\n\n```\n{exc}\n```")
    st.stop()

charter_hubs = sorted(data["Hub"].unique()) if not data.empty else []
raw_titles = list(raw_sheets.keys())
all_tabs = charter_hubs + raw_titles
if not all_tabs:
    st.warning("No data found.")
    st.stop()

# ---- Main page: highlighted app banner ----
st.markdown("<div class='app-banner'>BJOC&nbsp;-&nbsp;ALL IN ONE DASHBOARD</div>",
            unsafe_allow_html=True)

# ---- Main page: sheet picker + refresh button (top of page) ----
pick_col, rf_col = st.columns([6, 1], vertical_alignment="bottom")
hub = pick_col.selectbox(
    "Sheet / Tab", all_tabs, key="hub_select",
    help="Only tabs that are visible (unhidden) in the sheet are listed.",
)
if rf_col.button("🔄 Refresh", use_container_width=True):
    get_data.clear()
    st.rerun()
if rf_sec and _HAS_AUTOREFRESH:
    st.caption(f"🟢 Live — auto-refreshing every {rf_choice}.")

# ---- Sidebar display controls (hub is known now) ----
st.sidebar.divider()
font_rem = st.sidebar.slider(
    "🔠 Table font size", min_value=0.6, max_value=1.5, value=0.9, step=0.05,
    help="Enlarge or shrink the table text.",
)
cell_w = st.sidebar.slider(
    "↔️ Data cell width", min_value=2.5, max_value=14.0,
    value=7.0 if hub in raw_sheets else 3.5, step=0.5,
    help="Widen or narrow the metric/date data columns in real time.",
)
label_w = st.sidebar.slider(
    "🏷️ Label (frozen) width", min_value=3.0, max_value=22.0, value=9.0, step=0.5,
    help="Width of the frozen Charter / Metric / Target (label) columns. "
         "Keep this small so the data columns stay prominent.",
)

# ---- Centered hub title (shared by both views; not sticky -> no overlap) ----
st.markdown(f"<div class='hub-title'>{hub}<span class='accent'></span></div>",
            unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# RAW (non-Charter) sheet view — e.g. BRSNR, Arkham Pendency View
# --------------------------------------------------------------------------- #
if hub in raw_sheets:
    rs = raw_sheets[hub]
    st.markdown(render_raw(rs["values"], rs["colors"], rs["frozen"], font_rem,
                           cell_w=cell_w, merges=rs.get("merges"), label_w=label_w),
                unsafe_allow_html=True)
    csv = "\n".join(
        ",".join('"' + str(c).replace('"', '""') + '"' for c in row)
        for row in rs["values"] if any(str(c).strip() for c in row)
    ).encode("utf-8")
    st.download_button("⬇️ Download (CSV)", csv, f"{hub}.csv", "text/csv")
    st.stop()

# --------------------------------------------------------------------------- #
# CHARTER hub view (Overall / Day / Week / Month)
# --------------------------------------------------------------------------- #
hub_df = data[data["Hub"] == hub].copy()

charters_in_order = (
    hub_df.sort_values("Order")[["Charter"]].drop_duplicates()["Charter"].tolist()
)
sel_charters = st.sidebar.multiselect("Charter(s)", charters_in_order,
                                      default=charters_in_order)
if sel_charters:
    hub_df = hub_df[hub_df["Charter"].isin(sel_charters)]

# freeze settings come straight from the sheet (header row + label columns)
frozen_cols = int(hub_df["FrozenCols"].iloc[0]) if len(hub_df) else 3

all_dates = [pd.Timestamp(d) for d in
             sorted(pd.to_datetime(hub_df["Date"].dropna().unique()).to_pydatetime())]

st.sidebar.divider()
st.sidebar.caption(
    f"**{hub}**\n\n{hub_df['Metric'].nunique()} metrics · {len(all_dates)} days\n\n"
    f"{all_dates[0]:%d %b} → {all_dates[-1]:%d %b %Y}" if all_dates else f"**{hub}**"
)

if not all_dates:
    st.warning("No dated data for this tab.")
    st.stop()

tab_over, tab_day, tab_week, tab_month = st.tabs(
    ["Overall", "Day", "Week", "Month"]
)

# --------------------------------------------------------------------------- #
# 🗂️ OVERALL — most recent N days
# --------------------------------------------------------------------------- #
with tab_over:
    ndays = min(4, len(all_dates))
    recent = all_dates[-ndays:]
    st.markdown(render_sheet(hub_df, recent, frozen_cols=frozen_cols,
                             font_rem=font_rem, cell_w=cell_w, label_w=label_w),
                unsafe_allow_html=True)
    csv = hub_df[hub_df["Date"].isin(recent)][
        ["Charter", "Metric", "Target_raw", "Date", "Value_raw"]
    ].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download (CSV)", csv, f"{hub}_last{ndays}d.csv", "text/csv")

# --------------------------------------------------------------------------- #
# 📅 DAY
# --------------------------------------------------------------------------- #
with tab_day:
    sel_day = st.selectbox(
        "Pick a date", list(reversed(all_dates)),
        format_func=lambda d: pd.Timestamp(d).strftime("%A, %d %b %Y"),
    )
    sel_day = pd.Timestamp(sel_day)
    prev_day = max([d for d in all_dates if d < sel_day], default=None)

    delta_map = {}
    if prev_day is not None:
        prev_vals = {r["Order"]: r["Value"]
                     for _, r in hub_df[hub_df["Date"] == prev_day].iterrows()}
        for _, r in hub_df[hub_df["Date"] == sel_day].iterrows():
            pv = prev_vals.get(r["Order"])
            if pv is not None and pd.notna(pv) and pd.notna(r["Value"]):
                diff = r["Value"] - pv
                if abs(diff) > 1e-9:
                    txt = f"{diff*100:+.1f} pp" if r["IsPercent"] else f"{diff:+,.0f}"
                    bg = "#d9ead3" if diff > 0 else "#f4cccc"   # green up / red down
                    delta_map[int(r["Order"])] = (txt, bg)

    st.markdown(render_sheet(hub_df, [sel_day], delta_map=delta_map,
                             frozen_cols=frozen_cols, font_rem=font_rem,
                             cell_w=cell_w, label_w=label_w), unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# 🗓️ WEEK
# --------------------------------------------------------------------------- #
with tab_week:
    week_keys = sorted({(int(d.isocalendar().year), int(d.isocalendar().week))
                        for d in all_dates}, reverse=True)

    def week_label(key):
        yr, wk = key
        days = [d for d in all_dates
                if (int(d.isocalendar().year), int(d.isocalendar().week)) == key]
        return (f"Week {wk}, {yr}  ·  {min(days):%d %b} – {max(days):%d %b}"
                if days else f"Week {wk}, {yr}")

    sel_week = st.selectbox("Pick a week number", week_keys, format_func=week_label)
    wk_days = [d for d in all_dates
               if (int(d.isocalendar().year), int(d.isocalendar().week)) == sel_week]
    st.markdown(render_sheet(hub_df, wk_days, frozen_cols=frozen_cols,
                             font_rem=font_rem, cell_w=cell_w, label_w=label_w),
                unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# 📆 MONTH
# --------------------------------------------------------------------------- #
with tab_month:
    month_keys = sorted({(d.year, d.month) for d in all_dates}, reverse=True)
    sel_month = st.selectbox(
        "Pick a month", month_keys,
        format_func=lambda k: pd.Timestamp(year=k[0], month=k[1], day=1).strftime("%B %Y"),
    )
    mo_days = [d for d in all_dates if (d.year, d.month) == sel_month]
    st.markdown(render_sheet(hub_df, mo_days, frozen_cols=frozen_cols,
                             font_rem=font_rem, cell_w=cell_w, label_w=label_w),
                unsafe_allow_html=True)
    csv = hub_df[hub_df["Date"].isin(mo_days)][
        ["Charter", "Metric", "Target_raw", "Date", "Value_raw"]
    ].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download this month (CSV)", csv,
                       f"{hub}_{sel_month[0]}-{sel_month[1]:02d}.csv", "text/csv")
