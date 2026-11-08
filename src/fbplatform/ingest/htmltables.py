"""Small helpers: Wikipedia rendered HTML -> section/table grids with rowspan/colspan resolved, plus entity extraction from cells."""
from __future__ import annotations

import json
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

API = "https://en.wikipedia.org/w/api.php"


def page_html(c, title: str):
    r = c.get(f"{API}?action=parse&format=json&formatversion=2&redirects=1&prop=text%7Crevid&disablelimitreport=1&page={quote(title)}")
    j = json.loads(r.content)
    if "parse" not in j:
        return None
    return j["parse"]["text"], j["parse"]["revid"], j["parse"]["title"]


def txt(el) -> str:
    for s in el.select("sup.reference, .mw-editsection, style"):
        s.decompose()
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def grid(table):
    """list of rows, each a list of cell elements with rowspan/colspan expanded (same element repeated)."""
    rows, spans = [], {}
    for r, tr in enumerate(table.find_all("tr")):
        row, c = [], 0
        cells = tr.find_all(["th", "td"], recursive=False)
        it = iter(cells)
        while True:
            while (r, c) in spans:
                row.append(spans.pop((r, c)))
                c += 1
            cell = next(it, None)
            if cell is None:
                break
            rs, cs = int(re.sub(r"\D", "", cell.get("rowspan", "1")) or 1), int(re.sub(r"\D", "", cell.get("colspan", "1")) or 1)
            for k in range(cs):
                row.append(cell)
                for d in range(1, rs):
                    spans[(r + d, c)] = cell
                c += 1
        while (r, c) in spans:
            row.append(spans.pop((r, c)))
            c += 1
        rows.append(row)
    return rows


def sections(html: str):
    """yield (h2, h3, table_element) for every wikitable in document order."""
    soup = BeautifulSoup(html, "lxml")
    h2 = h3 = None
    for el in soup.find_all(["h2", "h3", "table"]):
        if el.name == "h2":
            h2, h3 = txt(el).replace("[edit]", "").strip(), None
        elif el.name == "h3":
            h3 = txt(el).replace("[edit]", "").strip()
        elif "wikitable" in " ".join(el.get("class", [])):
            yield h2, h3, el


def entities(cell) -> list[dict]:
    """links inside a cell, skipping references/anchors; flag links are remembered as the country of the next link."""
    out, country = [], None
    for a in cell.find_all("a"):
        href = a.get("href", "")
        title = a.get("title")
        if not title or href.startswith("#") or re.match(r"(File|Help|Wikipedia|Category|Template):", title) or a.find_parent("sup"):
            continue
        if a.find_parent(class_=re.compile("flagicon")) or (a.find("img") and not a.get_text(strip=True)):
            country = re.sub(r"\s+(men's )?national .*$", "", title, flags=re.I)
            continue
        out.append(dict(link=title, display=a.get_text(strip=True), country=country))
    return out
