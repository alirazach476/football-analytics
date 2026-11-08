"""Master competition/season registry (Phase 3 seed).

Policy: only tournament-level facts that are confirmed are stored; everything else is None.
Every row carries `verification_status`:
  - seeded_unverified : typed in by the maintainer from public knowledge; the coverage audit
                        cross-checks it against sources but it is NOT yet checked against the
                        official source. Treat as provisional.
  - scheduled         : future edition; only confirmed scheduling facts present.
`expected_matches_basis` explains how expected_matches was derived so it can be challenged.
Qualifying rounds are out of scope for the first pass (expected counts exclude them).
"""
from __future__ import annotations

import pandas as pd

from .config import REGISTRY_DIR

COMPETITIONS = [
    dict(competition_id="WC", competition_name="FIFA World Cup", competition_type="national_team_tournament",
         confederation="FIFA", country_or_region="World", official_source="https://www.fifa.com"),
    dict(competition_id="EURO", competition_name="UEFA European Championship", competition_type="national_team_tournament",
         confederation="UEFA", country_or_region="Europe", official_source="https://www.uefa.com"),
    dict(competition_id="COPA", competition_name="Copa América", competition_type="national_team_tournament",
         confederation="CONMEBOL", country_or_region="South America", official_source="https://www.conmebol.com"),
    dict(competition_id="UNL", competition_name="UEFA Nations League", competition_type="national_team_league",
         confederation="UEFA", country_or_region="Europe", official_source="https://www.uefa.com"),
]

# (year, host, start, end, teams, expected_matches, format)
_WC = [
    (2002, "South Korea; Japan", "2002-05-31", "2002-06-30", 32, 64, "8 groups of 4, then knockout"),
    (2006, "Germany", "2006-06-09", "2006-07-09", 32, 64, "8 groups of 4, then knockout"),
    (2010, "South Africa", "2010-06-11", "2010-07-11", 32, 64, "8 groups of 4, then knockout"),
    (2014, "Brazil", "2014-06-12", "2014-07-13", 32, 64, "8 groups of 4, then knockout"),
    (2018, "Russia", "2018-06-14", "2018-07-15", 32, 64, "8 groups of 4, then knockout"),
    (2022, "Qatar", "2022-11-20", "2022-12-18", 32, 64, "8 groups of 4, then knockout"),
    (2026, "Canada; Mexico; United States", "2026-06-11", "2026-07-19", 48, 104, "12 groups of 4, then round of 32 knockout"),
]
_EURO = [
    (2000, "Belgium; Netherlands", "2000-06-10", "2000-07-02", 16, 31),   # added 2026-11-06 at the project owner's request
    (2004, "Portugal", "2004-06-12", "2004-07-04", 16, 31),
    (2008, "Austria; Switzerland", "2008-06-07", "2008-06-29", 16, 31),
    (2012, "Poland; Ukraine", "2012-06-08", "2012-07-01", 16, 31),
    (2016, "France", "2016-06-10", "2016-07-10", 24, 51),
    (2020, "Multiple (pan-European; held 2021)", "2021-06-11", "2021-07-11", 24, 51),
    (2024, "Germany", "2024-06-14", "2024-07-14", 24, 51),
    (2028, "United Kingdom; Ireland", None, None, 24, 51),
]
_COPA = [  # (year, host, start, end, teams, expected)
    (2001, "Colombia", "2001-07-11", "2001-07-29", 12, 26),   # added 2026-11-06 at the project owner's request
    (2004, "Peru", "2004-07-06", "2004-07-25", 12, 26),
    (2007, "Venezuela", "2007-06-26", "2007-07-15", 12, 26),
    (2011, "Argentina", "2011-07-01", "2011-07-24", 12, 26),
    (2015, "Chile", "2015-06-11", "2015-07-04", 12, 26),
    (2016, "United States", "2016-06-03", "2016-06-26", 16, 32),  # Copa América Centenario
    (2019, "Brazil", "2019-06-14", "2019-07-07", 12, 26),
    (2021, "Brazil", "2021-06-13", "2021-07-10", 10, 28),
    (2024, "United States", "2024-06-20", "2024-07-14", 16, 32),
]
_UNL_FINALS = {"2018-19": ("Portugal", 2019), "2020-21": ("Italy", 2021),
               "2022-23": ("Netherlands", 2023), "2024-25": ("Spain", 2025)}


def _ucl_season_label(y: int) -> str:
    return f"{y}-{str(y + 1)[2:]}"


def build_registry() -> pd.DataFrame:
    rows = []
    comp = {c["competition_id"]: c for c in COMPETITIONS}

    def add(cid, season_id, edition, host=None, start=None, end=None, teams=None, fmt=None,
            expected=None, basis=None, status="seeded_unverified", stages=None, groups=None):
        rows.append({**comp[cid], "season_id": season_id, "tournament_edition": edition,
                     "start_date": start, "end_date": end, "host_country": host,
                     "participating_teams_count": teams, "competition_format": fmt,
                     "number_of_stages": stages, "number_of_groups": groups,
                     "expected_matches": expected, "expected_matches_basis": basis,
                     "verification_status": status})

    for y, host, s, e, n, m, fmt in _WC:
        fut = y >= 2026
        add("WC", f"WC-{y}", f"{y} FIFA World Cup", host, s, e, n, fmt, m,
            "format arithmetic (excludes qualifying)", "scheduled" if fut else "seeded_unverified",
            stages=2, groups=12 if y == 2026 else 8)
    for y, host, s, e, n, m in _EURO:
        fmt = "4 groups of 4 + QF/SF/F" if n == 16 else "6 groups of 4 (best thirds advance), R16 onward"
        add("EURO", f"EURO-{y}", f"UEFA Euro {y}", host, s, e, n, fmt, m,
            "format arithmetic (excludes qualifying)", "scheduled" if y >= 2028 else "seeded_unverified",
            stages=2, groups=4 if n == 16 else 6)
    for y, host, s, e, n, m in _COPA:
        add("COPA", f"COPA-{y}", f"Copa América {y}", host, s, e, n, None, m, "format arithmetic")
    # Copa América 2028: no confirmed information held -> all null, flagged for manual check.
    add("COPA", "COPA-2028", "Copa América 2028", status="scheduled")
    # Scope (set by the project owner on 2026-11-05): FIFA World Cup, UEFA Euro, Copa America, UEFA Nations League.
    # The UEFA Champions League was removed from scope.
    for sid, (host, yr) in _UNL_FINALS.items():
        add("UNL", f"UNL-{sid}", f"{sid} UEFA Nations League", f"{host} (Finals {yr})")
    add("UNL", "UNL-2026-27", "2026-27 UEFA Nations League", status="scheduled")
    return pd.DataFrame(rows)


def write_registry() -> pd.DataFrame:
    df = build_registry()
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(REGISTRY_DIR / "competition_seasons.csv", index=False)
    df.to_parquet(REGISTRY_DIR / "competition_seasons.parquet", index=False)
    return df
