import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while b := f.read(1 << 22):
            h.update(b)
    return h.hexdigest()


def test_original_raw_files_are_unchanged_since_they_were_registered():
    """Every file under data/raw re-hashes to the SHA-256 recorded in the Bronze register (latest version): originals were never modified."""
    h = pd.read_csv(ROOT / "data" / "bronze" / "ingestion_history.csv")
    latest = h.sort_values("version").groupby("path").tail(1)
    raw = latest[latest.origin == "raw"]
    assert len(raw) > 900
    bad = [r.path for r in raw.itertuples() if (ROOT / r.path).exists() and _sha(ROOT / r.path) != r.sha256]
    assert bad == [], f"modified originals: {bad[:5]}"
    missing = [r.path for r in raw.itertuples() if not (ROOT / r.path).exists()]
    assert missing == [], f"registered originals missing: {missing[:5]}"


def test_bronze_snapshots_are_read_only_and_ucl_files_kept_but_flagged():
    snap = sorted((ROOT / "data" / "bronze" / "collected").glob("v*"))[-1]
    files = list(snap.iterdir())
    assert len(files) >= 14 and all(not os.access(f, os.W_OK) for f in files)
    h = pd.read_csv(ROOT / "data" / "bronze" / "ingestion_history.csv")
    ucl = h[h.excluded_ucl]
    assert len(ucl) >= 197 and all((ROOT / p).exists() for p in ucl.path)                # kept on disk, never deleted


def test_no_champions_league_anywhere_downstream():
    for name in ("matches", "teams", "events", "lineups", "squads", "awards"):
        d = pd.read_parquet(ROOT / "data" / "silver" / f"{name}.parquet")
        if "competition_id" in d.columns:
            assert set(d.competition_id.dropna()) <= {"WC", "EURO", "COPA", "UNL"}
        for c in d.select_dtypes("object").columns:
            if "season" in c or "competition" in c:
                assert not d[c].dropna().astype(str).str.contains(r"UCL|Champions League", case=False).any()


def test_notebooks_were_executed_and_contain_no_errors():
    nbs = sorted((ROOT / "notebooks").glob("*.ipynb"))
    assert len(nbs) >= 5
    for p in nbs:
        nb = json.loads(p.read_text(encoding="utf-8"))
        code = [c for c in nb["cells"] if c["cell_type"] == "code"]
        assert code and all(c.get("outputs") is not None for c in code)
        assert not any(o.get("output_type") == "error" for c in code for o in c["outputs"]), p.name
        assert sum(len(c["outputs"]) for c in code) >= 5, f"{p.name} has no executed outputs"


REQUIRED_DOCS = ["README.md", "docs/ARCHITECTURE.md", "docs/DATA_DICTIONARY.md", "docs/DATA_SOURCES.md", "docs/DATA_QUALITY.md", "docs/DATABASE_SCHEMA.md",
                 "docs/PIPELINE_GUIDE.md", "docs/DATA_SCIENCE_REPORT.md", "docs/MODEL_DOCUMENTATION.md", "docs/DASHBOARD_GUIDE.md"]


def test_all_ten_required_documents_exist_and_are_substantial():
    for d in REQUIRED_DOCS:
        p = ROOT / d
        assert p.exists() and len(p.read_text(encoding="utf-8")) > 1500, d


def test_documents_state_the_key_rules():
    r = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Coming soon" in r and "Champions League" in r and "never modified" in r
    assert "prediction" in (ROOT / "docs" / "DASHBOARD_GUIDE.md").read_text(encoding="utf-8").lower()
    assert "Fjelstul" in (ROOT / "docs" / "DATA_SOURCES.md").read_text(encoding="utf-8") and "terms prohibit" in (ROOT / "docs" / "DATA_SOURCES.md").read_text(encoding="utf-8")


def test_generated_docs_list_every_warehouse_table():
    from fbplatform.dashboard.queries import WH_TABLES
    dd = (ROOT / "docs" / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
    sc = (ROOT / "docs" / "DATABASE_SCHEMA.md").read_text(encoding="utf-8")
    for t in WH_TABLES:
        assert f"wh.{t}" in dd and f"| {t} |" in sc, t


def test_requirements_cover_every_third_party_import():
    stdlib = set(sys.stdlib_module_names)
    mapping = {"sklearn": "scikit-learn", "bs4": "beautifulsoup4", "yaml": "pyyaml", "psycopg": "psycopg", "mwparserfromhell": "mwparserfromhell", "fbplatform": None, "pytest": "pytest"}
    reqs = {re.split(r"[<>=\[]", ln.strip(), maxsplit=1)[0].lower() for ln in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")}
    optional = {"kaleido"}                                   # imported inside try/except and documented as optional in requirements.txt
    assert all(o in (ROOT / "requirements.txt").read_text(encoding="utf-8") for o in optional)
    missing = set()
    for p in (ROOT / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            mods = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else ([node.module.split(".")[0]] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else [])
            for m in mods:
                if m in stdlib or m == "__future__":
                    continue
                pkg = mapping.get(m, m)
                if pkg and pkg.lower() not in reqs and m not in optional:
                    missing.add(m)
    assert not missing, f"imports not covered by requirements.txt: {sorted(missing)}"


def test_every_source_file_compiles_and_every_module_imports():
    """Guards against broken files such as a mis-indented import in the (network) pipeline module."""
    import importlib
    import py_compile
    for p in (ROOT / "src").rglob("*.py"):
        py_compile.compile(str(p), doraise=True)
    skip = {"fbplatform.dashboard.app"}                       # streamlit entry points run st.* at import time
    for p in (ROOT / "src" / "fbplatform").rglob("*.py"):
        mod = ".".join(p.relative_to(ROOT / "src").with_suffix("").parts)
        if mod.endswith("__init__") or mod in skip or ".views." in mod or mod.endswith("_defs"):
            continue
        importlib.import_module(mod)
    importlib.import_module("fbplatform.orchestration.dagster_defs")
