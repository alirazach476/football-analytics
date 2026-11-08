"""StatsBomb Open Data. competitions.json / matches / events are fetched and inspected, not assumed."""
from __future__ import annotations

import json

from .base import row

RAW = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
URL = "https://github.com/statsbomb/open-data"
NAMES = {"FIFA World Cup": "WC", "UEFA Euro": "EURO", "Copa America": "COPA"}   # scope: no club competitions
LICENSE_NOTE = "StatsBomb open-data user agreement: attribution to StatsBomb required (see LICENSE.pdf in repo)"


def season_id(cid, season_name):
    if cid == "UCL":
        a, b = season_name.split("/")
        return f"UCL-{a}-{b[2:]}"
    return f"{cid}-{season_name}"


def audit(client, registry) -> list[dict]:
    comps = json.loads(client.get(f"{RAW}/competitions.json").content)
    idx = {}
    for c in comps:
        cid = NAMES.get(c["competition_name"])
        if cid and c.get("competition_gender", "male") == "male":
            idx[season_id(cid, c["season_name"])] = c
    rows = []
    for _, rg in registry.iterrows():
        sid = rg["season_id"]
        unl = rg["competition_id"] == "UNL"
        if unl or sid not in idx:
            rows.append(row(rg, "StatsBomb Open Data", URL, None, None if unl else 0, None, "absent",
                            "Nations League not listed in competitions.json" if unl
                            else "season not listed in competitions.json"))
            continue
        c = idx[sid]
        ms = json.loads(client.get(f"{RAW}/matches/{c['competition_id']}/{c['season_id']}.json").content)
        fields = {f"match.{k}" for k in ms[0]} if ms else set()
        ev = lu = 0
        for m in ms:
            ev += client.exists(f"{RAW}/events/{m['match_id']}.json")
            lu += client.exists(f"{RAW}/lineups/{m['match_id']}.json")
        has_loc = has_xg = False
        if ms and ev:
            events = json.loads(client.get(f"{RAW}/events/{ms[0]['match_id']}.json").content)
            fields |= {f"event_type.{e['type']['name']}" for e in events}
            has_loc = any("location" in e for e in events)
            has_xg = any("statsbomb_xg" in e.get("shot", {}) for e in events)
        if ev:
            fields.add("events")
        if lu:
            fields.add("lineups")
        if has_loc:
            fields.add("event.location")
        if has_xg:
            fields.add("shot.statsbomb_xg")
        res = sum(1 for m in ms if m.get("home_score") is not None)
        note = (f"{LICENSE_NOTE}; events file present for {ev}/{len(ms)} matches, lineups for {lu}/{len(ms)}; "
                f"event fields inspected on first match only (match_id={ms[0]['match_id'] if ms else None})")
        rows.append(row(rg, "StatsBomb Open Data", f"{URL}/tree/master/data/matches/{c['competition_id']}",
                        fields, len(ms), res, "checked", note))
    return rows
