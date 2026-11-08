"""Run the source discovery + coverage audit and write the matrix and a report."""
from __future__ import annotations

import pandas as pd

from .config import AUDIT_DIR
from .http import HttpClient
from .registry import write_registry
from .sources import footballdata_org, official, openfootball, statsbomb
from .sources.base import MATRIX_COLUMNS


def run() -> pd.DataFrame:
    reg = write_registry()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    gh = HttpClient("openfootball", 0.3)
    disc = openfootball.discover(gh)
    rows = openfootball.audit(gh, reg, disc)
    rows += statsbomb.audit(HttpClient("statsbomb", 0.05), reg)
    rows += footballdata_org.audit(lambda h: HttpClient("footballdata_org", 6.5, h), reg)
    rows += official.audit(reg)
    m = pd.DataFrame(rows)[MATRIX_COLUMNS]
    m.to_csv(AUDIT_DIR / "source_coverage_matrix.csv", index=False)
    m.to_parquet(AUDIT_DIR / "source_coverage_matrix.parquet", index=False)
    write_report(m, disc)
    return m


def write_report(m: pd.DataFrame, disc: dict):
    ok = m[m.check_status == "checked"]
    pv = ok.pivot_table(index="season_id", columns="source_name", values="collected_matches", aggfunc="max")
    exp = m.drop_duplicates("season_id").set_index("season_id")["expected_matches"]
    pv.insert(0, "expected", exp.reindex(pv.index))
    lines = ["# Source coverage audit", "", f"Generated {m.last_checked_at.max()}. Rows: {len(m)}.", "",
             "Expected counts are registry seeds (unverified against official sources) and exclude qualifying.",
             "", "## Collected matches per season (checked sources only; blank = not present)", "",
             pv.fillna("").to_markdown(), "", "## Status counts per source", "",
             m.groupby(["source_name", "check_status"]).size().unstack(fill_value=0).to_markdown(), "",
             "## OpenFootball repos (from GitHub API)", ""]
    lines += [f"- {k}: license={v['license']}, last push {v['pushed_at']}" for k, v in disc.items()]
    (AUDIT_DIR / "coverage_report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run()
