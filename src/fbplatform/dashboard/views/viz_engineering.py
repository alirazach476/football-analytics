import streamlit as st

from fbplatform.dashboard import queries as Q
from fbplatform.dashboard import viz_ui as U
from fbplatform.dashboard.lib import require_db
from fbplatform.viz import engineering as V

require_db()
st.title("Data-engineering visualisations")
st.caption("Pipeline health, completeness and coverage. Missing values are never shown as zero: genuine zeros (e.g. attendance 0 = closed doors) are reported separately.")


@st.cache_data(ttl=300, show_spinner=False)
def _load():
    return dict(lc=V.layer_counts(), log=V.pipeline_log(), dq=V.dq_log(), fr=V.freshness_rows(), cov=V.coverage(), dup=Q.duplicate_checks(), raw=V.raw_files(),
                m=V.silver_table("matches"), p=V.silver_table("players"), l=V.silver_table("lineups", ["match_id", "team_id", "player_id", "minutes_played_derived", "is_starter"]),
                v=V.silver_table("venues"), sq=V.silver_table("squads"), q=Q.q("select max(d.full_date)::text as d from wh.fact_matches m join wh.dim_date d using (date_key) where m.match_status='completed'").d.iloc[0])


d = _load()
tabs = st.tabs(["Layer record counts", "Completeness & missing values", "Duplicates", "Pipeline runs", "Freshness", "Source coverage", "Quality trends"])
with tabs[0]:
    U.render(V.layer_record_counts(d["lc"]), "e_layers")
    st.dataframe(d["raw"], hide_index=True, use_container_width=True)
    st.caption("Registered raw source files (Bronze) by source; UEFA Champions League files are flagged and excluded from processing, never deleted.")

with tabs[1]:
    n_up = int((d["m"].match_status != "completed").sum())
    m = d["m"][d["m"].match_status == "completed"]                       # fixtures not played yet are NOT data gaps: they are excluded from every missing-value measure
    st.info(f"Played matches only ({len(m):,}). The {n_up} 'Coming soon' fixtures are excluded here: their missing referee, attendance and score are expected, not data gaps.")
    U.render(V.missing_heatmap(m, ["attendance", "referee_raw", "venue_id", "man_of_the_match_raw", "home_score_ht", "home_score_ft90", "kickoff_time_local", "stage", "home_team_id"], "competition_id", "Missing values in matches, by competition", ["attendance"]), "e_miss_m")
    p = d["p"].assign(source_id_prefix=lambda x: x.player_id.str[:4])
    U.render(V.missing_heatmap(p, ["nationality", "date_of_birth", "height_cm", "preferred_foot", "primary_position"], "source_id_prefix", "Missing values in players, by source of the canonical id"), "e_miss_p")
    U.render(V.completeness_bars({"matches": m, "players": d["p"], "lineups": d["l"], "venues": d["v"], "squads": d["sq"]},
                                 {"matches": ["attendance", "referee_raw", "venue_id", "man_of_the_match_raw", "home_score_ht", "home_score_ft90"], "players": ["date_of_birth", "nationality", "primary_position", "height_cm"],
                                  "lineups": ["player_id", "minutes_played_derived"], "venues": ["latitude", "capacity"], "squads": ["date_of_birth", "caps", "club_raw"]}), "e_complete")

with tabs[2]:
    U.render(V.duplicates(d["dup"]), "e_dups")

with tabs[3]:
    U.render(V.pipeline_durations(d["log"]), "e_dur")
    U.render(V.pipeline_failures(d["log"]), "e_fail")
    failed = d["log"][d["log"].status == "failed"]
    with st.expander(f"Failed attempts ({len(failed)}) with their error text"):
        st.dataframe(failed[["run_id", "step", "attempt", "started_at", "detail"]], hide_index=True, use_container_width=True)

with tabs[4]:
    U.render(V.freshness(d["fr"], d["q"]), "e_fresh")

with tabs[5]:
    U.render(V.source_coverage(d["cov"]), "e_cov")

with tabs[6]:
    U.render(V.dq_trends(d["dq"]), "e_dq")
