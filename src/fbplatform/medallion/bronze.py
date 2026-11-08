"""Bronze layer: an immutable, versioned register of every source file plus a frozen snapshot of the collected dataset.

* Originals are NEVER modified or moved: data/raw/** (downloads) and data/processed/** (the collected dataset) stay where they are.
* Every file is registered with sha256, size, source, original name (URL for cached downloads), ingestion time and a version number.
  A file whose hash changed gets version n+1; an unchanged file adds nothing (idempotent).
* The collected-dataset tables the Silver layer reads are copied once into data/bronze/collected/v<n>/ (a new version only when a
  table's hash changed), so Silver is reproducible from a frozen input even if data/processed is rebuilt later.
* Files that belong to the excluded UEFA Champions League are registered (nothing is deleted) but flagged `excluded_ucl`
  and are never passed on to Silver.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone

import pandas as pd

from ..config import DATA, ROOT
from ..inventory import UCL_RE

BRONZE = DATA / "bronze"
HISTORY = BRONZE / "ingestion_history.csv"
COLLECTED = [
    "matches.parquet", "teams.parquet", "team_aliases.csv", "players_all.parquet", "lineups_all.parquet", "events_all.parquet",
    "player_match_stats_all.parquet", "team_match_stats_all.parquet", "venues.parquet", "match_event_coverage.csv",
    "squads/squads.parquet", "squads/head_coaches.parquet", "player_links.csv", "awards/awards.parquet",
]
EXTRA = [DATA / "registry" / "competition_seasons.csv"]
COLS = ["path", "original_name", "source", "sha256", "size_bytes", "version", "ingested_at", "excluded_ucl", "origin"]


def _sha(p, chunk=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def _manifest():
    m = {}
    f = DATA / "raw" / "manifest.jsonl"
    if f.exists():
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            m[hashlib.sha1(r["url"].encode()).hexdigest()] = r["url"]
    return m


def _history() -> pd.DataFrame:
    return pd.read_csv(HISTORY) if HISTORY.exists() else pd.DataFrame(columns=COLS)


def register() -> dict:
    """Register every raw download and every collected table. Returns counts. Idempotent."""
    BRONZE.mkdir(parents=True, exist_ok=True)
    hist = _history()
    seen = hist.groupby("path").agg(last_sha=("sha256", "last"), version=("version", "max")) if len(hist) else pd.DataFrame(columns=["last_sha", "version"])
    manifest = _manifest()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new, unchanged = [], 0
    files = [(p, "raw") for p in sorted((DATA / "raw").rglob("*")) if p.is_file() and p.name != "manifest.jsonl"]
    files += [(DATA / "processed" / c, "collected") for c in COLLECTED if (DATA / "processed" / c).exists()]
    files += [(p, "collected") for p in EXTRA if p.exists()]
    for p, origin in files:
        rel = p.relative_to(ROOT).as_posix()
        sha = _sha(p)
        if rel in seen.index and seen.loc[rel, "last_sha"] == sha:
            unchanged += 1
            continue
        version = int(seen.loc[rel, "version"]) + 1 if rel in seen.index else 1
        url = manifest.get(p.name) if origin == "raw" else None
        src = p.relative_to(DATA / "raw").parts[0] if origin == "raw" else "collected_dataset"
        new.append(dict(path=rel, original_name=url or p.name, source=src, sha256=sha, size_bytes=p.stat().st_size, version=version,
                        ingested_at=now, excluded_ucl=bool(UCL_RE.search(url or "")), origin=origin))
    if new:
        out = pd.concat([hist, pd.DataFrame(new)], ignore_index=True)
        out.to_csv(HISTORY, index=False)
    with open(BRONZE / "ingestion.log", "a", encoding="utf-8") as lg:
        lg.write(f"{now} registered={len(new)} unchanged={unchanged} total_files={len(files)}\n")
    return dict(registered=len(new), unchanged=unchanged, total=len(files), ucl_flagged=int(sum(r["excluded_ucl"] for r in new)))


def snapshot_collected() -> str:
    """Copy the collected tables into data/bronze/collected/v<n>/ when any of them changed since the last snapshot."""
    root = BRONZE / "collected"
    root.mkdir(parents=True, exist_ok=True)
    versions = sorted(int(d.name[1:]) for d in root.glob("v*") if d.is_dir())
    srcs = [DATA / "processed" / c for c in COLLECTED if (DATA / "processed" / c).exists()] + [p for p in EXTRA if p.exists()]
    if versions:
        last = root / f"v{versions[-1]}"
        same = all((last / p.name).exists() and _sha(last / p.name) == _sha(p) for p in srcs)
        if same:
            return f"v{versions[-1]} (unchanged)"
    nv = (versions[-1] + 1) if versions else 1
    dst = root / f"v{nv}"
    dst.mkdir()
    for p in srcs:
        shutil.copy2(p, dst / p.name)
    for f in dst.iterdir():
        f.chmod(0o444)                                   # read-only: Bronze is never edited
    return f"v{nv}"


def latest_snapshot():
    root = BRONZE / "collected"
    versions = sorted(int(d.name[1:]) for d in root.glob("v*") if d.is_dir())
    if not versions:
        raise RuntimeError("no Bronze snapshot yet: run python -m fbplatform.medallion.bronze")
    return root / f"v{versions[-1]}"


if __name__ == "__main__":
    print(register())
    print("snapshot:", snapshot_collected())
