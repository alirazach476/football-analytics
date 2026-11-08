"""football-data.org v4. Requires a free API key (FOOTBALL_DATA_API_KEY); no auth is bypassed.

Without a key nothing about this source is claimed: every row is `not_verified`. With a key we
query /v4/competitions to see what the account tier actually exposes, then count matches per
season. The free tier is limited (about 10 requests/minute), which min_interval enforces.
NOTE: the keyed path has not been exercised yet (no key available when written).
"""
from __future__ import annotations

import json
import os

from .base import row

BASE = "https://api.football-data.org/v4"
CODES = {"WC": "WC", "EURO": "EC", "UCL": "CL"}  # Copa/UNL unknown until the API lists them


def audit(client_factory, registry) -> list[dict]:
    key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not key:
        return [row(rg, "football-data.org", "https://www.football-data.org", None, None, None, "not_verified",
                    "FOOTBALL_DATA_API_KEY not set; coverage unknown (not assumed)")
                for _, rg in registry.iterrows()]
    c = client_factory({"X-Auth-Token": key})
    listing = json.loads(c.get(f"{BASE}/competitions").content)["competitions"]
    avail = {x["code"] for x in listing}
    rows = []
    for _, rg in registry.iterrows():
        code = CODES.get(rg["competition_id"])
        if code not in avail:
            rows.append(row(rg, "football-data.org", BASE, None, None, None, "not_in_account_tier",
                            "competition not returned by /v4/competitions for this key"))
            continue
        year = rg["season_id"].split("-")[1]
        url = f"{BASE}/competitions/{code}/matches?season={year}"
        try:
            r = c.get(url)
            ms = json.loads(r.content)["matches"] if r is not None else []
        except Exception as e:  # restricted seasons return errors
            rows.append(row(rg, "football-data.org", BASE, None, None, None, "restricted", f"unusable response: {e}"))
            continue
        fields = set(ms[0]) if ms else set()
        res = sum(1 for m in ms if m["score"]["fullTime"]["home"] is not None)
        rows.append(row(rg, "football-data.org", url, fields, len(ms), res, "checked",
                        "fields = top-level keys of first match object"))
    return rows
