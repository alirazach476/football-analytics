import pandas as pd
import pytest

from fbplatform.config import DATA
from fbplatform.ingest import es_wikipedia as E
from fbplatform.ingest import venues as V

P = DATA / "processed"


@pytest.mark.parametrize("text,expected", [
    ("| capacity = 88,966", 88966), ("| capacity = 60,000<ref>x</ref>", 60000),
    ("| capacity = {{nowrap|81,044}} (football)", 81044), ("| capacity = ", None), ("| capacity = 500", None)])   # < 1,000 is not a stadium capacity
def test_capacity_parsing(text, expected):
    assert V._capacity(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("{{coord|51.556|-0.2796}}", (51.556, -0.2796)),
    ("{{Coord|41|18|53|N|19|51|8|E|display=inline,title}}", (41 + 18 / 60 + 53 / 3600, 19 + 51 / 60 + 8 / 3600)),
    ("{{coord|-15.6|-56.1|region:BR_type:landmark|display=inline,title}}", (-15.6, -56.1)),
    ("no template here", (None, None))])
def test_coordinate_parsing(text, expected):
    lat, lon = V._coord_from_text(text)
    assert (lat, lon) == pytest.approx(expected) if expected[0] is not None else (lat, lon) == expected


def test_spanish_match_template_with_bold_markers_and_missing_data():
    txt = """{{Partidos
|id=ROU_NIR |local=Ruman\u00eda |pa\u00edslocal=ROU
|resultado = \'\'\'1:1\'\'\' (1:0)
|pa\u00edsvisita = NIR |visita = Irlanda del Norte
|fecha = {{fecha|7|9|2020}}, 20:45 |asistencia = 0 |reporte = x }}
{{Partidos |local = {{self-d|BRA}} |resultado = 0:0 |visita = {{selb|VEN}} |fecha = 3 de julio de 2011, 16:00 |asistencia = 35&nbsp;000 }}
{{Partidos |local = {{self-d|ARG}} |resultado = 0:0 |visita = {{selb|COL}} |fecha = 6 de julio de 2011, 21:45 |asistencia = Sin datos sobre }}"""
    r = E.parse_page(txt)
    assert [(x["home"][0], x["away"][0], x["score"], x["attendance"]) for x in r] == [
        ("ROU", "NIR", (1, 1), 0), ("BRA", "VEN", (0, 0), 35000), ("ARG", "COL", (0, 0), None)]   # 0 = closed doors; "Sin datos" stays null


need = pytest.mark.skipif(not (P / "venues.parquet").exists(), reason="run the pipeline first")


@need
def test_every_match_has_a_venue_except_the_unnamed_london_fixtures():
    m = pd.read_parquet(P / "matches.parquet")
    played = m[m.match_status == "completed"]
    assert played.venue_id.notna().all()                                     # every played match
    left = m[m.venue_id.isna()]
    assert set(left.match_status) == {"scheduled"} and len(left) <= 4 and left.venue_raw.str.contains("Tottenham").all()
    assert set(m.venue_link_rule.dropna()) <= {"match_box_hyperlink", "tournament_host_venue_map"}


@need
def test_venue_table_integrity():
    v = pd.read_parquet(P / "venues.parquet")
    m = pd.read_parquet(P / "matches.parquet")
    assert v.venue_id.is_unique and v.wikipedia_title.is_unique
    assert m.venue_id.dropna().isin(v.venue_id).all()
    assert v.latitude.dropna().between(-90, 90).all() and v.longitude.dropna().between(-180, 180).all()
    assert v.capacity.dropna().ge(1000).all()
    assert v.venue_name.notna().all() and (v.n_matches > 0).all()
    # a venue is a stadium, never a bare city page: it needs a capacity or coordinates, except the unfinished Newcastle stadium
    bare = v[v.capacity.isna() & v.latitude.isna()]
    assert set(bare.venue_name) <= {"Newcastle United Stadium"}


@need
def test_attendance_provenance_and_gaps():
    m = pd.read_parquet(P / "matches.parquet")
    played = m[m.match_status == "completed"]
    assert played.attendance[played.attendance_source.isna()].isna().all()          # every attendance carries its source
    es = played[played.attendance_source.fillna("").str.startswith("es.")]
    assert len(es) == 12 and set(es.season_id) == {"COPA-2011"}                      # rounded estimates, labelled
    assert played.attendance.isna().sum() == 8                                       # recorded nowhere in either Wikipedia
