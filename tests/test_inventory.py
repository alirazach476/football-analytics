import hashlib

import pandas as pd
import pytest

from fbplatform import inventory as I
from fbplatform.config import DATA


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_profile_frame_reports_shape_nulls_duplicates_dates_keys_and_coverage():
    df = pd.DataFrame({"match_id": ["a", "b", "c", "c"], "season_id": ["WC-2018"] * 4, "competition_id": ["WC"] * 4,
                       "match_date": ["2018-06-14", "2018-06-15", None, None], "score": [1.0, None, 2.0, 2.0]})
    p = I.profile_frame(df)
    assert p["records"] == 4 and p["columns"] == 5
    assert p["full_row_duplicates"] == 1                                  # the two 'c' rows are identical
    assert p["date_ranges"]["match_date"] == ["2018-06-14", "2018-06-15"]
    assert p["coverage"] == {"competition_id": ["WC"], "season_id": ["WC-2018"]}
    assert p["candidate_primary_keys"] == []                              # match_id repeats, so it is not a key
    assert {c["column"]: c["nulls"] for c in p["column_profile"]}["score"] == 1


def test_ucl_files_are_recognised_by_their_source_url():
    assert I.UCL_RE.search("https://raw.githubusercontent.com/openfootball/europe-champions-league/master/2013-14/cl.txt")
    assert I.UCL_RE.search("https://en.wikipedia.org/w/api.php?page=2018%E2%80%9319%20UEFA%20Champions%20League")
    assert not I.UCL_RE.search("https://raw.githubusercontent.com/openfootball/euro/master/2016--france/euro.txt")


def test_descriptions_come_from_the_project_dictionary_only():
    d = I.descriptions()
    assert "match_id" in d and "FBM-" in d["match_id"]                    # harvested from docs/data_dictionary_matches.md
    assert all(isinstance(v, str) and len(v) > 5 for v in d.values())


need = pytest.mark.skipif(not (DATA / "inventory" / "issues.csv").exists(), reason="run python -m fbplatform.initial_quality first")


@need
def test_inventory_never_modifies_source_data():
    f = DATA / "processed" / "matches.parquet"
    before = sha(f)
    I.descriptions()                                                      # reads docs only
    pd.read_csv(DATA / "inventory" / "dataset_inventory.csv")
    assert sha(f) == before


@need
def test_initial_quality_report_is_complete_and_excludes_ucl():
    iss = pd.read_csv(DATA / "inventory" / "issues.csv")
    assert set(iss.classification) <= {"confirmed_error", "possible_error", "legitimate_missing", "info"}
    assert set(range(1, 16)) <= set(iss.question)                          # all 15 investigation questions answered
    ucl = iss[iss.question == 0].iloc[0]
    assert ucl.records == 0                                                # no Champions League rows in any processed table
    assert (DATA / "inventory" / "data_quality_initial_report.html").exists() and (DATA / "inventory" / "data_dictionary.xlsx").exists()
    inv = pd.read_csv(DATA / "inventory" / "dataset_inventory.csv")
    assert not inv.notes.fillna("").str.contains("UNREADABLE").any()       # every file could be read, none skipped silently
