"""Prepare the files the hosted API ships with (run on the machine that has the warehouse, before committing):

  * deploy/cache/*.pkl                 heavy API caches (scoring the test period, SHAP, player stats ...), so the free host does not recompute them
  * data/layer_counts_snapshot.json    Bronze file row counts and the big silver event table count (those files are not shipped)

    PYTHONPATH=src python tools/prepare_render.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "FB_CACHE_DIR": str(ROOT / "deploy" / "cache"), "MLFLOW_DISABLE_AGENT_HINT": "1"}
    if subprocess.run([sys.executable, "-m", "fbplatform.api.warm"], env=env).returncode:
        sys.exit("cache warm-up failed (is the warehouse running?)")
    rows = []
    snaps = sorted((ROOT / "data" / "bronze" / "collected").glob("v*"))
    for f in sorted(snaps[-1].iterdir()) if snaps else []:
        if f.suffix == ".parquet":
            rows.append(dict(layer="Bronze (frozen snapshot)", table=f.stem, rows=pq.ParquetFile(f).metadata.num_rows))
        elif f.suffix == ".csv":
            rows.append(dict(layer="Bronze (frozen snapshot)", table=f.stem, rows=sum(1 for _ in open(f, encoding="utf-8", errors="ignore")) - 1))
    for f in sorted((ROOT / "data" / "silver").glob("*.parquet")):
        rows.append(dict(layer="Silver", table=f.stem, rows=pq.ParquetFile(f).metadata.num_rows))
    (ROOT / "data" / "layer_counts_snapshot.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"snapshot: {len(rows)} tables")


if __name__ == "__main__":
    main()
