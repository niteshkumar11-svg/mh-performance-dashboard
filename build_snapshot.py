"""
One-off: turn the exported sheet dump into ops_dashboard/data/snapshot.csv.

The dump is the whole workbook rendered as markdown tables (all tabs stacked).
We reconstruct the cell grid from the markdown, split it into per-block grids
(separated by blank lines), and run the same parser the live app uses. Each
Charter block becomes a "Hub" labelled by its order of appearance.

Run once:  python build_snapshot.py  "<path-to-dump.txt>"
"""
import json
import sys
from pathlib import Path

import pandas as pd

from data_loader import parse_grid, SNAPSHOT_PATH


def md_line_to_cells(line: str) -> list[str]:
    """'| a | b |' -> ['a','b'] keeping interior empties, dropping outer pipes."""
    if "|" not in line:
        return [line.strip()] if line.strip() else []
    parts = [c.strip() for c in line.split("|")]
    # drop the empty artefacts created by the leading/trailing pipe
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def main(dump_path: str) -> None:
    raw = Path(dump_path).read_text(encoding="utf-8")
    try:
        content = json.loads(raw)["fileContent"]
    except (json.JSONDecodeError, KeyError):
        content = raw  # already plain text

    lines = content.split("\n")

    # Split into blocks on blank lines so each Charter table is parsed with its
    # own hub label (mirrors per-worksheet reading in live mode).
    blocks: list[list[list[str]]] = []
    cur: list[list[str]] = []
    for ln in lines:
        if ln.strip() == "":
            if cur:
                blocks.append(cur)
                cur = []
            continue
        cur.append(md_line_to_cells(ln))
    if cur:
        blocks.append(cur)

    frames = []
    hub_idx = 0
    for grid in blocks:
        # only bother if this block looks like a Charter table
        flat_first = (grid[0][0].lower() if grid and grid[0] else "")
        if flat_first != "charter":
            continue
        hub_idx += 1
        frames.append(parse_grid(grid, hub_label=f"Hub {hub_idx}"))

    frames = [f for f in frames if not f.empty]
    if not frames:
        print("No Charter blocks found — nothing written.")
        return

    df = pd.concat(frames, ignore_index=True)
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SNAPSHOT_PATH, index=False)

    print(f"Wrote {len(df):,} tidy rows -> {SNAPSHOT_PATH}")
    print(f"Hubs:      {sorted(df['Hub'].unique())}")
    print(f"Charters:  {sorted(df['Charter'].unique())}")
    print(f"Date range:{df['Date'].min()} .. {df['Date'].max()}")
    print(f"Metrics:   {df['Metric'].nunique()} distinct")
    print("\nSample:")
    print(df.head(8).to_string(index=False))


if __name__ == "__main__":
    default = (
        r"C:\Users\nitesh.kumar11\.claude\projects"
        r"\C--Users-nitesh-kumar11-Desktop-Python-Scripts"
        r"\15f47273-7a07-44b6-8f30-1b0cead92435\tool-results"
        r"\mcp-f7f4483e-b952-4033-b6dd-964c14a81837-read_file_content-1781605419884.txt"
    )
    main(sys.argv[1] if len(sys.argv) > 1 else default)
