"""FIFA / UEFA / CONMEBOL official records.

None of these publishes a documented open API or data licence that this project has verified.
We therefore (a) record the robots.txt HTTP status for transparency and (b) mark every season
`not_assessed`. No scraping is performed; official data would enter via manual, licensed exports
or the cross-check workflow in a later phase.
"""
from __future__ import annotations

import requests

from ..config import USER_AGENT
from .base import row

SITES = {"WC": ("FIFA official records", "https://www.fifa.com"),
         "UCL": ("UEFA official records", "https://www.uefa.com"),
         "EURO": ("UEFA official records", "https://www.uefa.com"),
         "UNL": ("UEFA official records", "https://www.uefa.com"),
         "COPA": ("CONMEBOL official records", "https://www.conmebol.com")}


def robots_status() -> dict:
    out = {}
    for name, base in set(SITES.values()):
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=20)
            out[name] = f"robots.txt HTTP {r.status_code}"
        except Exception as e:
            out[name] = f"robots.txt unreachable ({type(e).__name__})"
    return out


# Terms reviewed 2026-11-05 (text read from the live pages; wording quoted, not paraphrased into permission).
TERMS = {
    "FIFA official records": "terms clause 6.6 (inside.fifa.com/terms-of-service): may not use 'robots, spiders or other automated programmes' on FIFA Digital Platforms -> NOT collected",
    "UEFA official records": "terms 6.2 (uefa.com/termsconditions): 'prohibited from using automated tools, such as robots, spiders, or scripts, to scrape or collect Content' and no systematic compilation into a 'database' -> NOT collected",
    "CONMEBOL official records": "www.conmebol.com reachable but no robots.txt (404) and no terms page found; copaamerica.com does not resolve -> permission unverified, NOT collected",
}


def audit(registry) -> list[dict]:
    rb = robots_status()
    rows = []
    for _, rg in registry.iterrows():
        name, base = SITES[rg["competition_id"]]
        rows.append(row(rg, name, base, None, None, None, "not_assessed",
                        f"{rb[name]}; {TERMS[name]}; manual licensed export would be needed"))
    return rows
