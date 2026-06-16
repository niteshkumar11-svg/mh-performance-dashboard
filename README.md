# 📦 Ops KPI Dashboard

Interactive Streamlit dashboard over the daily **Charter / Metrics** Google
Sheet — Volume, Reliability, Quality, People, Cost and Loss KPIs per hub.

It reproduces the sheet faithfully — metrics as rows (in sheet order), dates as
columns, **merged Charter cells**, and **the sheet's own background colours /
conditional formatting** — across four time views:

| View | What it shows |
|------|---------------|
| 🗂️ **Overall** | the most recent **7 / 14 / 21 / 30** days side by side |
| 📅 **Day** | one date, all metrics, with a **day-on-day change** column (green↑ / red↓) |
| 🗓️ **Week** | pick a **week number** → every day in that week, date-wise |
| 📆 **Month** | pick a **month** → every day in that month, date-wise |

Only worksheet tabs that are **visible (not hidden)** in the sheet are loaded.

The sheet is not a single clean table: each hub is a wide block shaped
`Charter | Metric | Target | <one column per day>`. `data_loader.py` reads each
visible tab's values **and cell colours** via the Sheets REST API and melts
every block into one tidy DataFrame, so adding hubs/metrics needs no code
changes.

---

## Quick start (works immediately — uses the bundled snapshot)

```powershell
cd "C:\Users\nitesh.kumar11\Desktop\Python Scripts\ops_dashboard"
python -m pip install -r requirements.txt
streamlit run app.py
```

The app opens at <http://localhost:8501> using `data/snapshot.csv` (a real
export of the sheet). No credentials needed to explore.

---

## Enable LIVE data (reads the Google Sheet on demand)

1. **Google Cloud Console** → create/select a project.
2. **Enable APIs**: *Google Sheets API* and *Google Drive API*.
3. **Create a service account** → add a **JSON key** and download it.
4. Copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` and paste
   the JSON fields into the `[gcp_service_account]` block.
5. **Share the Google Sheet** with the service account's `client_email`
   (Viewer is enough).
6. Restart the app — a **“Live (Google Sheets)”** option appears in the sidebar.
   Use **🔄 Refresh data** to pull the latest (cached 15 min).

---

## Refreshing the bundled snapshot

If you stay on snapshot mode and want newer numbers, re-export the sheet and run:

```powershell
python build_snapshot.py "path\to\sheet_export.txt"
```

It accepts either the raw JSON dump (`{"fileContent": "..."}`) or plain markdown
tables, rebuilds `data/snapshot.csv`, and prints a summary.

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI — Overview, Trends, Attainment heatmap, Hub comparison, Data |
| `data_loader.py` | Parser + live (gspread) and snapshot loaders |
| `build_snapshot.py` | Rebuild `data/snapshot.csv` from an export |
| `data/snapshot.csv` | Bundled tidy data (offline/demo) |
| `requirements.txt` | Python dependencies |
| `.streamlit/secrets.toml.example` | Template for live-mode credentials |

## Notes
- In **live** mode each worksheet tab is read separately and tagged by its tab
  name, so hubs show their real names. In **snapshot** mode they are labelled
  `Hub 1…N` in order of appearance.
- Percentages (e.g. `113.50%`) are stored as fractions (`1.135`) and formatted
  back to `%` in the UI. Non-numeric cells (`DNF`, blanks) become `NaN`.
