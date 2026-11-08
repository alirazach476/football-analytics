import pandas as pd
import plotly.express as px
import streamlit as st

from fbplatform.dashboard.lib import cached, fig, require_db

require_db()
st.title("Player analytics")
st.warning("Numbers cover only the collected competitions (not careers). Goals are goals linked to a player id: Nations League scorers are not linked, and assists exist only where the sources record them (mainly StatsBomb-covered editions). Minutes are approximate for Wikipedia-based editions.", icon="ℹ️")

tab_search, tab_top, tab_cmp = st.tabs(["Player profile", "Top lists", "Compare players"])

with tab_search:
    term = st.text_input("Search a player (name contains)", "Messi")
    res = cached("player_search", term) if len(term) >= 2 else pd.DataFrame()
    if res.empty:
        st.info("No player found. Try another spelling.")
    else:
        pick = st.selectbox("Player", res.player_key, format_func=lambda k: f"{res.set_index('player_key').loc[k, 'full_name']} ({res.set_index('player_key').loc[k, 'nationality'] or 'nationality n/a'})")
        prof = cached("player_profile", pick).iloc[0]
        by = cached("player_by_edition", pick)
        c = st.columns(5)
        c[0].metric("Appearances", int(by.appearances.sum()))
        c[1].metric("Goals", int(by.goals.sum()))
        c[2].metric("Assists (where recorded)", int(by.assists.sum()))
        c[3].metric("Minutes (known)", f"{by.minutes_played.sum():,.0f}")
        c[4].metric("Tournaments", by.season_id.nunique())
        st.caption(f"Position (where known): {prof.primary_position or 'n/a'} · Date of birth: {prof.date_of_birth or 'n/a'} · merged from {int(prof.n_source_ids)} source id(s)")
        fig(px.bar(by, x="season_id", y="goals", hover_data=["team_name", "appearances", "minutes_played"], title="Goals by tournament"))
        st.dataframe(by, hide_index=True, use_container_width=True)
        aw = cached("player_awards", pick)
        if len(aw):
            st.markdown("**Individual awards** (source: Wikipedia award pages)")
            st.dataframe(aw, hide_index=True, use_container_width=True)

with tab_top:
    metric = st.radio("Rank by", ["goals", "assists", "appearances", "minutes_played"], horizontal=True)
    top = cached("top_players", metric, 25)
    if metric == "assists":
        st.caption("Assists are a partial measure (see warning above).")
    fig(px.bar(top.iloc[::-1], x=metric, y="full_name", orientation="h", hover_data=["nationality", "tournaments"], labels={"full_name": ""}))
    st.dataframe(top, hide_index=True, use_container_width=True)

with tab_cmp:
    c1, c2 = st.columns(2)
    t1, t2 = c1.text_input("Player 1", "Ronaldo"), c2.text_input("Player 2", "Messi")
    r1, r2 = cached("player_search", t1), cached("player_search", t2)
    if len(r1) and len(r2):
        p1 = c1.selectbox("Pick 1", r1.player_key, format_func=lambda k: r1.set_index("player_key").loc[k, "full_name"], key="p1")
        p2 = c2.selectbox("Pick 2", r2.player_key, format_func=lambda k: r2.set_index("player_key").loc[k, "full_name"], key="p2")
        a, b = cached("player_by_edition", p1).assign(player=r1.set_index("player_key").loc[p1, "full_name"]), cached("player_by_edition", p2).assign(player=r2.set_index("player_key").loc[p2, "full_name"])
        both = pd.concat([a, b])
        fig(px.line(both, x="season_id", y="goals", color="player", markers=True, title="Goals by tournament"))
        tot = both.groupby("player")[["appearances", "goals", "assists", "minutes_played"]].sum().reset_index()
        tot["goals_per_appearance"] = (tot.goals / tot.appearances.replace(0, pd.NA)).round(3)
        st.dataframe(tot, hide_index=True, use_container_width=True)
        st.caption("Different positions, eras and competitions: totals are not a verdict on who is better.")
    else:
        st.info("Search for two players.")
