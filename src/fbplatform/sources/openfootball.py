"""OpenFootball (CC0). Verified by listing the GitHub repo trees and reading the files.

Two layouts exist: structured JSON (openfootball/worldcup.json, euro.json) and loose
Football.TXT text (worldcup, euro, copa-america, europe-champions-league). JSON counts are exact.
TXT counts come from a line heuristic (see count_txt_matches) that is validated in tests against
known tournament totals; rows derived from it say so in `notes`.
"""
from __future__ import annotations

import json
import re

from .base import row

GH = "https://github.com/openfootball"
RAW = "https://raw.githubusercontent.com/openfootball"
API = "https://api.github.com/repos/openfootball"
REPOS = ["worldcup", "worldcup.json", "euro", "euro.json", "copa-america", "europe-champions-league"]

SCORE = re.compile(r"\s\d+-\d+(\s|$)")
VS = re.compile(r"\s(v|vs)\s", re.I)
HT = re.compile(r"\(\d+-\d+\)")
SKIP_FIRST = "#=▪("  # comment, title, section marker (black small square), goal-detail line


def count_txt_matches(text: str) -> tuple[int, int]:
    """Return (match_lines, lines_with_score). Skips comments, headers, goal-detail lines."""
    n = played = 0
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s[0] in SKIP_FIRST or (s.startswith("Group ") and "|" in s):
            continue
        has_score = bool(SCORE.search(" " + s + " "))
        if has_score or VS.search(s):
            n += 1
            played += has_score
    return n, played


def _tree(client, repo):
    r = client.get(f"{API}/{repo}/git/trees/master?recursive=1")
    return [t["path"] for t in json.loads(r.content)["tree"] if t["type"] == "blob"]


def discover(client) -> dict:
    """Repo metadata + file lists, straight from the GitHub API."""
    out = {}
    for repo in REPOS:
        meta = json.loads(client.get(f"{API}/{repo}").content)
        out[repo] = {"license": (meta.get("license") or {}).get("spdx_id"), "pushed_at": meta["pushed_at"],
                     "files": _tree(client, repo)}
    return out


def _json_info(client, repo, path):
    r = client.get(f"{RAW}/{repo}/master/{path}")
    ms = json.loads(r.content)["matches"]
    fields = set()
    for m in ms:
        fields |= set(m)
        if isinstance(m.get("score"), dict):
            fields |= {f"score.{k}" for k in m["score"]}
        elif isinstance(m.get("score"), list):
            fields.add("score.ft(list form)")  # older files: score = [home, away], period not stated

    def has_result(m):
        s = m.get("score")
        return bool(s.get("ft")) if isinstance(s, dict) else bool(s) if isinstance(s, list) else False

    results = sum(has_result(m) for m in ms)
    return len(ms), results, fields


def _txt_info(client, repo, path):
    text = client.get(f"{RAW}/{repo}/master/{path}").content.decode("utf-8", "replace")
    n, played = count_txt_matches(text)
    f = {"teams", "date"}
    if played:
        f.add("score.ft")
    if HT.search(text):
        f.add("score.ht(observed)")
    if "@" in text:
        f.add("venue(observed)")
    if re.search(r"^\s*\(.*\d", text, re.M):
        f.add("goal_scorers(observed)")
    return n, played, f


def locate(cid, sid, files):
    """Find (repo, path, kind) for a registry season, or None."""
    yr = sid.split("-")[1]
    if cid == "WC":
        p = f"{yr}/worldcup.json"
        if p in files["worldcup.json"]:
            return ("worldcup.json", p, "json")
        for f in sorted(files["worldcup"]):
            if f.startswith(f"{yr}--") and f.endswith("/cup.txt"):
                return ("worldcup", f, "txt")
    elif cid == "EURO":
        p = f"{yr}/euro.json"
        if p in files["euro.json"]:
            return ("euro.json", p, "json")
        folder = "2021" if yr == "2020" else yr  # Euro 2020 was played in 2021; repo folder is 2021--europe
        for f in sorted(files["euro"]):
            if f.startswith(f"{folder}--") and f.endswith("/euro.txt"):
                return ("euro", f, "txt")
    elif cid == "COPA":
        for f in sorted(files["copa-america"]):
            if f.startswith(f"{yr}--") and f.endswith("/copa.txt"):
                return ("copa-america", f, "txt")
    elif cid == "UCL":
        p = f"{yr}-{sid.split('-')[2]}/cl.txt"
        if p in files["europe-champions-league"]:
            return ("europe-champions-league", p, "txt")
    return None


def audit(client, registry, disc) -> list[dict]:
    files = {repo: set(d["files"]) for repo, d in disc.items()}
    lic = {repo: d["license"] for repo, d in disc.items()}
    rows = []
    for _, rg in registry.iterrows():
        cid, sid = rg["competition_id"], rg["season_id"]
        hit = locate(cid, sid, files)
        if hit is None:
            unl = cid == "UNL"
            rows.append(row(rg, "OpenFootball", GH, None, None if unl else 0, None, "absent",
                            "no Nations League data found in the openfootball repos searched" if unl
                            else "no file for this season in the verified repo trees"))
            continue
        repo, path, kind = hit
        n, res, fields = (_json_info if kind == "json" else _txt_info)(client, repo, path)
        how = "exact count from JSON" if kind == "json" else "count via TXT line heuristic (validated by tests), not an exact parse"
        rows.append(row(rg, "OpenFootball", f"{GH}/{repo}/blob/master/{path}", fields, n, res, "checked",
                        f"license={lic[repo]}; {how}; file={path}"))
    return rows
