from __future__ import annotations

from datetime import datetime, timezone

MATRIX_COLUMNS = ["competition_id", "season_id", "source_name", "source_url", "available_fields",
                  "expected_matches", "collected_matches", "matches_with_results", "missing_matches",
                  "coverage_percentage", "last_checked_at", "check_status", "notes"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def row(reg_row, source_name, source_url=None, fields=None, collected=None, with_results=None,
        status="not_assessed", notes=""):
    exp = reg_row["expected_matches"]
    exp = None if exp is None or exp != exp else int(exp)
    missing = cov = None
    if exp is not None and collected is not None:
        missing = max(exp - collected, 0)
        cov = round(100 * min(collected, exp) / exp, 1)
    return {"competition_id": reg_row["competition_id"], "season_id": reg_row["season_id"],
            "source_name": source_name, "source_url": source_url,
            "available_fields": ";".join(sorted(fields)) if fields else None,
            "expected_matches": exp, "collected_matches": collected, "matches_with_results": with_results,
            "missing_matches": missing, "coverage_percentage": cov, "last_checked_at": now(),
            "check_status": status, "notes": notes}
