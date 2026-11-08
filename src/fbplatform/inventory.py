"""Part A: dataset inventory + initial data-quality investigation.  READ-ONLY on every source file.

Outputs (data/inventory/): dataset_inventory.csv / .json, data_dictionary.xlsx, data_quality_initial_report.html,
issues.csv (every finding classified: confirmed_error | possible_error | legitimate_missing | info).

Hash-named files in data/raw/<source>/ are cached HTTP responses (one file per URL); they are summarised per source and labelled
with their URL from data/raw/manifest.jsonl, which also flags files that belong to the EXCLUDED UEFA Champions League.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path

import pandas as pd

from .config import DATA, ROOT

OUT = DATA / "inventory"
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules", "inventory"}
TABULAR = {".csv", ".parquet", ".xlsx", ".xls"}
UCL_RE = re.compile(r"champions(?:[-_ ]|%20|\+)league|UCL", re.I)      # also matches percent-encoded Wikipedia URLs


def _manifest():
    m = {}
    f = DATA / "raw" / "manifest.jsonl"
    if f.exists():
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            m[hashlib.sha1(r["url"].encode()).hexdigest()] = r["url"]
    return m


def profile_frame(df: pd.DataFrame) -> dict:
    n = len(df)
    cols = []
    for c in df.columns:
        s = df[c]
        try:
            nun = int(s.nunique(dropna=True))
        except TypeError:
            nun = None
        nulls = int(s.isna().sum())
        sample = s.dropna().iloc[0] if nulls < n else None
        cols.append(dict(column=str(c), dtype=str(s.dtype), nulls=nulls, null_pct=round(100 * nulls / n, 2) if n else 0.0,
                         n_unique=nun, sample=str(sample)[:60] if sample is not None else None))
    try:
        dups = int(df.astype(str).duplicated().sum()) if n < 300_000 else int(df.duplicated().sum())
    except Exception:
        dups = None
    dates = {}
    for c in df.columns:
        if "date" in str(c).lower() or str(df[c].dtype).startswith("datetime"):
            d = pd.to_datetime(df[c], errors="coerce")
            if d.notna().any():
                dates[str(c)] = [str(d.min().date()), str(d.max().date())]
    cov = {k: sorted(map(str, df[k].dropna().unique()))[:60] for k in ("competition_id", "season_id") if k in df.columns}
    keys = [c["column"] for c in cols if n and c["nulls"] == 0 and c["n_unique"] == n and not c["dtype"].startswith("float")][:3]
    return dict(records=n, columns=len(df.columns), column_profile=cols, full_row_duplicates=dups, date_ranges=dates,
                coverage=cov, candidate_primary_keys=keys)


def inventory() -> tuple[pd.DataFrame, dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = _manifest()
    rows, frames, colrows = [], {}, []
    cache_summary = {}
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.parts):
            continue
        rel = p.relative_to(ROOT).as_posix()
        ext = p.suffix.lower()
        base = dict(path=rel, filename=p.name, format=ext.lstrip(".") or "(none)", size_bytes=p.stat().st_size, layer_hint=None,
                    records=None, columns=None, column_names=None, dtypes=None, nulls_total=None, full_row_duplicates=None,
                    date_range=None, competitions=None, seasons=None, candidate_primary_keys=None, notes="")
        parts = rel.split("/")
        # ---- hash-named HTTP cache blobs and per-match staging files: summarised, not profiled one by one
        if parts[:2] == ["data", "raw"] and len(parts) == 4 and not ext:
            src = parts[2]
            url = manifest.get(p.name)
            c = cache_summary.setdefault(src, dict(files=0, bytes=0, ucl_files=0))
            c["files"] += 1
            c["bytes"] += base["size_bytes"]
            if url and UCL_RE.search(url):
                c["ucl_files"] += 1
            continue
        if parts[:2] == ["data", "staging"]:
            c = cache_summary.setdefault("staging(" + parts[2] + ")", dict(files=0, bytes=0, ucl_files=0))
            c["files"] += 1
            c["bytes"] += base["size_bytes"]
            continue
        try:
            if ext == ".parquet":
                df = pd.read_parquet(p)
            elif ext == ".csv":
                df = pd.read_csv(p, low_memory=False, encoding="utf-8-sig")
            elif ext in (".xlsx", ".xls"):
                df = pd.read_excel(p)
            elif ext == ".json":
                raw = json.load(open(p, encoding="utf-8"))
                if isinstance(raw, list) and raw and isinstance(raw[0], dict):
                    df = pd.json_normalize(raw[:200000])
                else:
                    base["records"] = len(raw) if hasattr(raw, "__len__") else 1
                    base["notes"] = f"JSON {type(raw).__name__} (not a flat table)"
                    rows.append(base)
                    continue
            elif ext == ".zip":
                z = zipfile.ZipFile(p)
                base["records"] = len(z.namelist())
                base["notes"] = "archive members: " + ", ".join(z.namelist()[:8])
                rows.append(base)
                continue
            else:
                base["notes"] = "code/doc/config" if ext in (".py", ".md", ".toml", ".txt", ".example", ".out") else ""
                rows.append(base)
                continue
        except pd.errors.EmptyDataError:
            base["records"], base["columns"] = 0, 0
            base["notes"] = "empty file (no header, no rows)"
            rows.append(base)
            continue
        except Exception as e:  # unreadable files are reported, never skipped silently
            base["notes"] = f"UNREADABLE: {type(e).__name__}: {str(e)[:80]}"
            rows.append(base)
            continue
        prof = profile_frame(df)
        frames[rel] = df
        base.update(records=prof["records"], columns=prof["columns"], column_names=json.dumps([c["column"] for c in prof["column_profile"]]),
                    dtypes=json.dumps({c["column"]: c["dtype"] for c in prof["column_profile"]}),
                    nulls_total=int(sum(c["nulls"] for c in prof["column_profile"])), full_row_duplicates=prof["full_row_duplicates"],
                    date_range=json.dumps(prof["date_ranges"]), competitions=json.dumps(prof["coverage"].get("competition_id")),
                    seasons=json.dumps(prof["coverage"].get("season_id")), candidate_primary_keys=json.dumps(prof["candidate_primary_keys"]))
        if parts[:2] == ["data", "processed"] or parts[:2] == ["data", "registry"]:
            base["layer_hint"] = "current normalised output (becomes Silver/Gold in the new architecture)"
        elif parts[:2] == ["data", "raw"]:
            base["layer_hint"] = "raw download (Bronze candidate)"
        for c in prof["column_profile"]:
            colrows.append({"file": rel, **c})
        rows.append(base)
    inv = pd.DataFrame(rows)
    # foreign-key candidates: a *_id column whose name equals another file's candidate key
    pk_by_col = {}
    for r in inv.itertuples():
        for k in json.loads(r.candidate_primary_keys or "[]"):
            pk_by_col.setdefault(k, []).append(r.path)
    fk = []
    for r in inv.itertuples():
        for c in json.loads(r.column_names or "[]"):
            if c.endswith("_id") and c in pk_by_col and r.path not in pk_by_col[c]:
                fk.append(f"{c} -> {pk_by_col[c][0]}")
        fk_list = sorted(set(fk))
        fk = []
        inv.loc[inv.path == r.path, "foreign_key_candidates"] = json.dumps(fk_list)
    inv.to_csv(OUT / "dataset_inventory.csv", index=False)
    (OUT / "dataset_inventory.json").write_text(json.dumps(json.loads(inv.to_json(orient="records")), indent=1), encoding="utf-8")
    summary = dict(cache=cache_summary, ucl_cached_files=int(sum(c["ucl_files"] for c in cache_summary.values())))
    (OUT / "cache_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return inv, dict(frames=frames, columns=pd.DataFrame(colrows), cache=summary)


def descriptions() -> dict:
    """column -> meaning, harvested from the project's own markdown data dictionaries (no invention)."""
    d = {}
    for f in (ROOT / "docs").glob("*.md"):
        for line in open(f, encoding="utf-8"):
            m = re.match(r"\|\s*`?([a-z_0-9./ ]+?)`?\s*\|\s*(.{12,}?)\s*\|\s*$", line)
            if m and not set(m.group(1)) <= set("- "):
                d.setdefault(m.group(1).strip().split()[0], m.group(2).strip())
    return d


def write_dictionary(ctx: dict):
    desc = descriptions()
    col = ctx["columns"].copy()
    col["description"] = col.column.map(desc).fillna("(not yet documented)")
    with pd.ExcelWriter(OUT / "data_dictionary.xlsx", engine="openpyxl") as xw:
        pd.read_csv(OUT / "dataset_inventory.csv")[["path", "format", "records", "columns", "size_bytes", "candidate_primary_keys", "notes"]] \
            .to_excel(xw, "files", index=False)
        col.to_excel(xw, "columns", index=False)
    return col


if __name__ == "__main__":
    inv, ctx = inventory()
    col = write_dictionary(ctx)
    print(len(inv), "files inventoried |", len(ctx["frames"]), "tables profiled |", len(col), "columns |",
          "cache:", {k: (v["files"], v["ucl_files"]) for k, v in ctx["cache"].items()})
