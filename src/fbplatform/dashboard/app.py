"""Streamlit entry point:  streamlit run src/fbplatform/dashboard/app.py   (needs PYTHONPATH=src and the warehouse running)"""
import streamlit as st

st.set_page_config(page_title="Football analytics", page_icon="⚽", layout="wide", initial_sidebar_state="expanded")

analytics = [
    st.Page("views/overview.py", title="Overview", icon="🏠", default=True),
    st.Page("views/competition.py", title="Competition analysis", icon="🏆"),
    st.Page("views/teams.py", title="Team analytics", icon="🛡️"),
    st.Page("views/players.py", title="Player analytics", icon="👟"),
    st.Page("views/matches.py", title="Match analytics", icon="📅"),
    st.Page("views/ml.py", title="Machine learning", icon="🤖"),
    st.Page("views/data_engineering.py", title="Data engineering", icon="🛠️"),
]
lab = [
    st.Page("views/viz_competition.py", title="Competitions", icon="📊", url_path="viz-competitions"),
    st.Page("views/viz_team.py", title="Teams", icon="📈", url_path="viz-teams"),
    st.Page("views/viz_player.py", title="Players", icon="🎯", url_path="viz-players"),
    st.Page("views/viz_match.py", title="Matches", icon="⚽", url_path="viz-matches"),
    st.Page("views/viz_stats.py", title="Statistics", icon="📐", url_path="viz-statistics"),
    st.Page("views/viz_ml.py", title="Machine learning", icon="🧠", url_path="viz-ml"),
    st.Page("views/viz_engineering.py", title="Data engineering", icon="🔧", url_path="viz-engineering"),
]
st.navigation({"Analytics": analytics, "Visualization lab": lab}).run()
