import pandas as pd
from fbplatform.config import DATA
from fbplatform.medallion import bronze, silver

S = DATA / "silver"


def test_bronze_idempotent_and_originals_untouched():
    before = len(pd.read_csv(bronze.HISTORY))
    assert bronze.register()["registered"] == 0
    assert len(pd.read_csv(bronze.HISTORY)) == before


def test_bronze_flags_ucl_not_deleted():
    h = pd.read_csv(bronze.HISTORY)
    assert h.excluded_ucl.sum() >= 197


def test_silver_keeps_every_match_and_labels_upcoming():
    b = pd.read_parquet(bronze.latest_snapshot() / "matches.parquet")
    m = pd.read_parquet(S / "matches.parquet")
    assert len(m) == len(b) and set(m.match_id) == set(b.match_id)
    up = m[~m.is_played]
    assert len(up) == 51 and (up.status_label == "Coming soon").all()
    assert up.home_score.isna().all() and up.away_score.isna().all()
    assert up.fixture_detail.notna().all()
    assert m[m.is_played].home_score.notna().all()


def test_silver_no_ucl():
    m = pd.read_parquet(S / "matches.parquet")
    assert set(m.competition_id) == {"WC", "EURO", "COPA", "UNL"}


def test_player_merge_keeps_every_original_id_and_rule():
    x = pd.read_parquet(S / "player_xref.parquet")
    p = pd.read_parquet(S / "players.parquet")
    b = pd.read_parquet(bronze.latest_snapshot() / "players_all.parquet")
    assert set(x.player_id_original) == set(b.player_id)
    assert set(x.canonical_player_id) == set(p.player_id)
    mg = x[x.player_id_original != x.canonical_player_id]
    assert len(mg) > 0 and mg.resolution_rule.isin(["D1_same_name_and_dob", "D2_name_subset_same_national_team"]).all()
    assert (mg.resolution_rule == "D2_name_subset_same_national_team").sum() > 100


def test_d2_merges_never_join_two_players_of_one_lineup_and_keep_brothers_apart():
    x = pd.read_parquet(S / "player_xref.parquet")
    l = pd.read_parquet(S / "lineups.parquet").dropna(subset=["player_id"])
    assert l.groupby(["match_id", "team_id"]).player_id.apply(lambda s: s.is_unique).all()   # no player twice in one line-up after merging
    p = pd.read_parquet(S / "players.parquet")
    for surname in ("Boateng", "Hazard"):
        assert p.full_name.str.contains(surname, na=False).sum() >= 2                       # brothers stay separate people
    assert p.full_name.str.contains("Messi", na=False).sum() == 1


def test_events_reference_canonical_players_and_assists_never_overwritten():
    e = pd.read_parquet(S / "events.parquet")
    p = set(pd.read_parquet(S / "players.parquet").player_id)
    assert e.player_id.dropna().isin(p).all()
    b = pd.read_parquet(bronze.latest_snapshot() / "events_all.parquet")
    a = e[e.assist_source == "martj42"]
    assert len(a) > 0 and b.set_index("event_id").loc[a.event_id, "assist_name_raw"].isna().all()
    assert len(e) == len(b)


def test_scorer_links_have_provenance_and_do_not_overwrite_ids():
    e = pd.read_parquet(S / "events.parquet")
    b = pd.read_parquet(bronze.latest_snapshot() / "events_all.parquet").set_index("event_id")
    linked = e[e.player_id_source == "squad_name_match"]
    assert len(linked) > 500
    assert b.loc[linked.event_id, "player_id"].isna().all()          # only events that had no player id were touched


def test_scorer_linker_precision_on_goals_with_known_scorer():
    m, sq, lu = (pd.read_parquet(S / f"{n}.parquet") for n in ("matches", "squads", "lineups"))
    e = pd.read_parquet(S / "events.parquet")
    g = e[(e.provider == "fjelstul") & (e.event_type == "goal") & e.player_name_raw.notna() & e.player_id.notna() & e.team_id.notna()].copy()
    truth = g.player_id.copy()
    g["player_id"] = None
    out, _ = silver.link_scorers(g, m, sq, lu)
    got = out.loc[g.index, "player_id"]
    done = got.notna()
    assert done.sum() > 500 and (got[done] == truth[done]).mean() >= 0.98


def test_escaped_names_are_decoded_and_raw_kept():
    assert silver.fix_escapes(chr(92) + "u00f3") == "ó" and silver.fix_escapes("Plain Name") == "Plain Name"
    p = pd.read_parquet(S / "players.parquet")
    assert not p.full_name.str.contains(chr(92) + "u00", regex=False, na=False).any()
    assert (p.full_name_raw.str.contains(chr(92) + "u00", regex=False, na=False)).sum() > 100       # originals preserved


def test_wikipedia_lineups_linked_with_provenance_and_no_duplicates():
    l = pd.read_parquet(S / "lineups.parquet")
    w = l[l.provider == "wikipedia"]
    assert w.player_id.notna().mean() > 0.95
    assert (w[w.player_id_source == "squad_name_match"].player_id.notna()).all()
    d = l[l.player_id.notna()].groupby(["match_id", "team_id", "player_id"]).size()
    assert (d > 1).sum() == 0


def test_derived_minutes_are_internally_consistent():
    l = pd.read_parquet(S / "lineups.parquet")
    m = pd.read_parquet(S / "matches.parquet").set_index("match_id")
    w = l[(l.provider == "wikipedia") & (l.minutes_basis == "wikipedia_sub_card_minutes_nominal_end")]
    ok = w.groupby(["match_id", "team_id"]).minutes_played_derived.sum()
    def regulation(mid):
        r = m.loc[mid]
        return str(r.went_extra_time) != "True" and pd.isna(r.home_pen) and pd.isna(r.shootout_winner_side) and r.score_basis != "aet"
    reg = ok[[regulation(i[0]) for i in ok.index]]
    assert (reg == 990).mean() > 0.85 and reg.between(850, 1030).all()           # 11 players x 90 min, minus red cards
