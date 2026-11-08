"""Match analytics charts. Event-level charts (shot maps, passing networks, timelines) are rendered ONLY from rows that really exist:
shot maps need shot events with coordinates (StatsBomb / Wyscout matches), passing networks need pass events WITH a recorded recipient (StatsBomb only),
score progression needs goal events that reproduce the recorded score. Nothing is interpolated or invented."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..analysis import data as D
from . import common as C
from .common import Chart, unavailable

SRC = "wh.fact_match_events / staging.stg_matches (warehouse)"


# ------------------------------------------------------------------ loaders
def load_match_events(match_key: int) -> pd.DataFrame:
    e = D.q("""select e.event_key, e.minute, e.minute_added, e.period, e.event_type, e.card, e.is_goal, e.is_penalty, e.is_own_goal, e.provider, t.team_name,
                      coalesce(p.full_name, e.player_name_raw) as player, coalesce(rp.full_name, e.related_player_name_raw) as other_player
               from wh.fact_match_events e left join wh.dim_team t using (team_key) left join wh.dim_player p on p.player_key = e.player_key
               left join wh.dim_player rp on rp.player_key = e.related_player_key
               where e.match_key = %s and e.minute is not null and (e.is_goal or e.card is not null or e.event_type in ('goal','own_goal_against','card','substitution','shot')) and e.event_type <> 'own_goal_for'
                 and coalesce(e.period, 0) <> 5 order by e.minute, e.event_key""", (int(match_key),))
    for c in ("is_goal", "is_penalty", "is_own_goal"):
        e[c] = e[c].eq(True)
    return e


def load_shots(match_keys: list[int] | None = None, season_id: str | None = None, team: str | None = None) -> pd.DataFrame:
    d = D.q("""select e.match_key, s.season_id, t.team_name, coalesce(p.full_name, e.player_name_raw) as player, e.minute, e.xg, e.outcome, e.is_goal, e.is_penalty, e.location_x, e.location_y,
                      e.coordinate_system, e.provider, m.home_team_display, m.away_team_display
               from wh.fact_match_events e join wh.fact_matches m using (match_key) join wh.dim_season s using (season_key) left join wh.dim_team t on t.team_key = e.team_key
               left join wh.dim_player p on p.player_key = e.player_key
               where e.event_type = 'shot' and e.location_x is not null and coalesce(e.period, 0) <> 5
                 and (%s::int[] is null or e.match_key = any(%s::int[])) and (%s::text is null or s.season_id = %s) and (%s::text is null or t.team_name = %s)""",
              (match_keys, match_keys, season_id, season_id, team, team))
    d["is_goal"] = d.is_goal.eq(True)
    d["xg"] = pd.to_numeric(d.xg, errors="coerce")
    return D._num(d, ["minute", "location_x", "location_y"])


def load_passes(match_key: int) -> pd.DataFrame:
    d = D.q("""select e.minute, e.team_key, t.team_name, e.player_key, coalesce(p.display_name, p.full_name, e.player_name_raw) as passer, e.related_player_key as recipient_key, coalesce(rp.display_name, rp.full_name, e.related_player_name_raw) as recipient,
                      e.location_x, e.location_y, e.coordinate_system, e.outcome, e.provider
               from wh.fact_match_events e left join wh.dim_team t using (team_key) left join wh.dim_player p on p.player_key = e.player_key left join wh.dim_player rp on rp.player_key = e.related_player_key
               where e.match_key = %s and e.event_type = 'pass' and e.location_x is not null""", (int(match_key),))
    return D._num(d, ["minute", "location_x", "location_y"])


def team_country() -> dict:
    return D.q("select team_name, country from staging.stg_teams").set_index("team_name").country.to_dict()


# ------------------------------------------------------------------ timelines
def _symbol(r) -> tuple[str, str]:
    if r.kind == "Goal":
        return "circle", "Goal"
    if r.kind == "Own goal":
        return "x", "Own goal"
    if r.kind == "Yellow":
        return "square", "Yellow card"
    if r.kind == "Red":
        return "square", "Red card"
    return "triangle-up", "Substitution"


def _kinds(e: pd.DataFrame) -> pd.DataFrame:
    d = e[~((e.event_type == "shot") & ~e.is_goal & e.card.isna())].copy()
    has_card = d.card.notna() | d.event_type.eq("card")
    d["kind"] = np.select([d.event_type.eq("own_goal_against") | d.is_own_goal, d.is_goal, has_card & d.card.fillna("").str.contains("Red|Second"), has_card], ["Own goal", "Goal", "Red", "Yellow"], "Substitution")
    return d.drop_duplicates(["minute", "kind", "team_name", "player"])


def event_timeline(m_row: pd.Series, e: pd.DataFrame) -> Chart:
    d = _kinds(e)
    if d.empty:
        return unavailable("event_timeline", "no minute-level events (goals, cards, substitutions) exist for this match in the collected data")
    teams = [m_row.home_team_name, m_row.away_team_name]
    colors = {"Goal": C.CAT[0], "Own goal": C.CAT[7], "Yellow": C.CAT[3], "Red": C.CAT[7], "Substitution": "#898781"}
    fig = go.Figure()
    for kind in ["Goal", "Own goal", "Yellow", "Red", "Substitution"]:
        s = d[d.kind == kind]
        if s.empty:
            continue
        fig.add_scatter(x=s.minute, y=s.team_name.map({t: i for i, t in enumerate(teams)}), mode="markers", name={"Yellow": "Yellow card", "Red": "Red card"}.get(kind, kind),
                        marker=dict(size=13 if kind == "Goal" else 11, color=colors[kind], symbol=_symbol(type("R", (), {"kind": kind}))[0], line=dict(color=C.SURFACE, width=2)),
                        customdata=np.c_[s.player.fillna("unknown"), s.other_player.fillna("")], hovertemplate="%{x}' · " + kind + "<br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>")
    fig.update_yaxes(tickvals=[0, 1], ticktext=teams, range=[-0.6, 1.6], showgrid=True)
    fig.add_vline(x=45, line=dict(color=C.GRID, width=1)); fig.add_vline(x=90, line=dict(color=C.GRID, width=1))
    C.style(fig, "Match event timeline", "Match minute", None, height=330)
    return Chart(fig, d[["minute", "kind", "team_name", "player", "other_player", "provider"]], len(d), SRC,
                 "Only events present in the source are drawn (goals exist for every match; cards and substitutions only where the source lists them). Vertical lines = half-time and full time.", name="event_timeline")


def goal_timeline(m_row: pd.Series, e: pd.DataFrame) -> Chart:
    g = _kinds(e)
    g = g[g.kind.isin(["Goal", "Own goal"])]
    if g.empty:
        return unavailable("goal_timeline", "this match has no goals with a recorded minute (a 0-0 draw, or minute data missing)")
    fig = go.Figure()
    teams = [m_row.home_team_name, m_row.away_team_name]
    for i, t in enumerate(teams):
        s = g[g.team_name == t]
        fig.add_scatter(x=s.minute, y=[i] * len(s), mode="markers+text", name=t, text=[f"{p or ''}" for p in s.player], textposition="top center", textfont=dict(size=10, color=C.INK2),
                        marker=dict(size=15, color=C.CAT[i], symbol=["x" if k == "Own goal" else "circle" for k in s.kind], line=dict(color=C.SURFACE, width=2)),
                        hovertemplate="%{x}' · %{text}<extra>" + t + "</extra>")
    fig.update_yaxes(tickvals=[0, 1], ticktext=teams, range=[-0.7, 1.7], showgrid=True)
    C.style(fig, "Goal timeline", "Match minute", None, height=300, legend=False)
    return Chart(fig, g[["minute", "kind", "team_name", "player"]], len(g), SRC, "× = own goal (team shown is the team of the event as recorded; own-goal attribution differs by source).", name="goal_timeline")


def score_progression(m_row: pd.Series, e: pd.DataFrame) -> Chart:
    g = _kinds(e)
    g = g[g.kind.isin(["Goal", "Own goal"])].sort_values("minute")
    ha, aw = m_row.home_team_name, m_row.away_team_name
    fh, fa = int(m_row.home_score), int(m_row.away_score)
    if fh + fa == 0:
        return unavailable("score_progression", "0-0: there is no score to progress")
    def run(own_credit_opponent: bool):
        sh, sa, steps = 0, 0, []
        for r in g.itertuples():
            scoring = (aw if r.team_name == ha else ha) if (r.kind == "Own goal" and own_credit_opponent) else r.team_name
            if scoring == ha:
                sh += 1
            elif scoring == aw:
                sa += 1
            steps.append((r.minute, sh, sa, r.player, scoring))
        return steps, (sh, sa)
    for flag in (True, False):
        steps, end = run(flag)
        if end == (fh, fa):
            break
    else:
        return unavailable("score_progression", f"goal events ({len(g)}) do not reproduce the recorded score {fh}-{fa} for this match, so a progression would be wrong")
    xs = [0] + [s[0] for s in steps] + [max(90, steps[-1][0])]
    hs, as_ = [0] + [s[1] for s in steps] + [steps[-1][1]], [0] + [s[2] for s in steps] + [steps[-1][2]]
    fig = go.Figure()
    for name, ys, col in ((ha, hs, C.CAT[0]), (aw, as_, C.CAT[1])):
        fig.add_scatter(x=xs, y=ys, mode="lines+markers", line_shape="hv", name=name, line=dict(color=col, width=2), marker=dict(size=7, color=col, line=dict(color=C.SURFACE, width=1.5)), hovertemplate="%{x}' · %{y} goals<extra>" + name + "</extra>")
    C.style(fig, "Score progression", "Match minute", "Goals scored so far", height=340)
    fig.update_yaxes(dtick=1, rangemode="tozero")
    data = pd.DataFrame(steps, columns=["minute", f"{ha}_goals", f"{aw}_goals", "scorer", "credited_to"])
    return Chart(fig, data, len(steps), SRC, "Rebuilt from goal events and verified to end at the recorded score; step lines (the score only changes at a goal).", name="score_progression")


# ------------------------------------------------------------------ distributions
def scoreline_heatmap(m: pd.DataFrame, max_goals: int = 5) -> Chart:
    d = m[m.home_score.notna()]
    if len(d) < 20:
        return unavailable("scoreline_heatmap", "fewer than 20 played matches in the selection")
    h, a = d.home_score.clip(upper=max_goals).astype(int), d.away_score.clip(upper=max_goals).astype(int)
    tab = pd.crosstab(h, a).reindex(index=range(max_goals + 1), columns=range(max_goals + 1), fill_value=0)
    lab = [str(i) if i < max_goals else f"{max_goals}+" for i in range(max_goals + 1)]
    fig = go.Figure(go.Heatmap(z=tab.values, x=lab, y=lab, colorscale=C.SEQ, text=tab.values, texttemplate="%{text}", xgap=2, ygap=2, colorbar=dict(title="matches"),
                               hovertemplate="team listed first %{y} – %{x} team listed second<br>%{z} matches<extra></extra>"))
    C.style(fig, "Scoreline frequency", "Goals of the team listed second", "Goals of the team listed first", legend=False, height=470)
    fig.update_yaxes(autorange="reversed")
    long = tab.stack().rename("matches").reset_index().rename(columns={"home_score": "goals_listed_first", "away_score": "goals_listed_second"})
    return Chart(fig, long, len(d), SRC, "0 is a real count (that score never happened). 'Listed first' is not 'home': tournament matches are mostly on neutral ground.", name="scoreline_heatmap")


def outcome_distribution(m: pd.DataFrame, by: str = "competition_id") -> Chart:
    d = m[m.home_score.notna()].copy()
    if len(d) < 10 or by not in d.columns:
        return unavailable("outcome_distribution", "fewer than 10 played matches in the selection")
    tab = d.groupby([by, "outcome"]).size().unstack(fill_value=0).reindex(columns=["home win", "draw", "away win"], fill_value=0)
    n = tab.sum(axis=1)
    pc = 100 * tab.div(n, axis=0)
    cats = list(pc.index)
    fig = go.Figure()
    for col, lab, color in (("home win", "Team listed first wins", C.OUTCOME_COLOR["win"]), ("draw", "Draw", C.OUTCOME_COLOR["draw"]), ("away win", "Team listed second wins", C.OUTCOME_COLOR["loss"])):
        fig.add_bar(x=[f"{c}<br>n={int(n[c])}" for c in cats], y=pc[col], name=lab, marker_color=color, customdata=tab[col], hovertemplate="%{x}<br>" + lab + ": %{y:.1f}% (%{customdata} matches)<extra></extra>")
    fig.update_layout(barmode="stack")
    C.style(fig, "Match outcome distribution", {"competition_id": "Competition", "season_id": "Edition", "stage_name": "Stage"}.get(by, by) + " (n = matches)", "Share of matches (%)")
    C.bar_gap(fig)
    fig.update_xaxes(tickangle=45 if len(cats) > 8 else 0)
    return Chart(fig, tab.assign(n=n, home_win_pct=pc["home win"].round(1), draw_pct=pc["draw"].round(1), away_win_pct=pc["away win"].round(1)).reset_index(), len(d), SRC,
                 "Result on the recorded score (extra time included, shoot-outs excluded: a shoot-out match counts as a draw).", name="outcome_distribution")


# ------------------------------------------------------------------ shot maps
def shot_map(shots: pd.DataFrame, title: str = "Shot map", color_by: str = "team") -> Chart:
    d = shots.dropna(subset=["location_x", "location_y"]) if len(shots) else shots
    if d.empty:
        return unavailable("shot_map", "no shot coordinates exist for the selection - only the 313 StatsBomb/Wyscout matches (WC 2018/22, Euro 2016/20/24, Copa 2024) have them")
    d = C.normalise_xy(d)
    teams = [t for t in d.team_name.dropna().unique()][:4]
    fig = C.pitch_figure(title, half=True)
    has_xg = d.xg.notna().any()
    for i, t in enumerate(teams):
        s = d[d.team_name == t]
        for goal in (False, True):
            x = s[s.is_goal == goal]
            if x.empty:
                continue
            size = (8 + 38 * x.xg.fillna(0.06).clip(upper=1)) if has_xg else pd.Series(11, index=x.index)
            fig.add_scatter(x=x.x, y=x.y, mode="markers", name=f"{t} – {'goal' if goal else 'no goal'}", legendgroup=t,
                            marker=dict(size=size, color=C.CAT[i] if goal else "rgba(0,0,0,0)", symbol="circle", line=dict(color=C.CAT[i], width=2.2)),
                            customdata=np.c_[x.player.fillna("unknown"), x.minute, x.xg.round(3).astype(object).where(x.xg.notna(), "n/a"), x.outcome.fillna("–"), x.provider],
                            hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}'<br>xG %{customdata[2]} · outcome %{customdata[3]}<br>source %{customdata[4]}<extra>" + t + "</extra>")
    prov = ", ".join(sorted(d.provider.dropna().unique()))
    note = ("Marker area = xG (StatsBomb). " if has_xg else "") + ("Wyscout shots carry no xG: markers are equal-sized. " if (d.provider == "wyscout").any() else "") + \
        "Filled = goal, hollow = no goal. Attacking half shown; each team attacks left→right (as recorded); coordinates normalised to 0–100 per axis (StatsBomb 120×80, Wyscout 0–100) - aspect ratio indicative."
    return Chart(fig, d[["season_id", "team_name", "player", "minute", "xg", "outcome", "is_goal", "x", "y", "provider"]].round(3), len(d), f"wh.fact_match_events ({prov})", note, name="shot_map")


# ------------------------------------------------------------------ passing network
def passing_network(passes: pd.DataFrame, team: str, upto_minute: float | None = None, min_pass_pair: int = 3) -> Chart:
    d = passes[(passes.team_name == team)]
    if d.empty:
        return unavailable("passing_network", f"no pass events for {team} in this match")
    if not (d.provider == "statsbomb").any() or d.recipient_key.notna().sum() < 50:
        return unavailable("passing_network", "pass recipients are recorded only in StatsBomb event data (WC 2018/22, Euro 2020/24, Copa 2024); this match has none, so no network is drawn")
    d = d[d.outcome.isna() & d.recipient_key.notna()]                     # StatsBomb: no outcome = completed pass
    if upto_minute is not None:
        d = d[d.minute <= upto_minute]
    d = C.normalise_xy(d)
    nodes = d.groupby(["player_key", "passer"]).agg(x=("x", "mean"), y=("y", "mean"), passes=("minute", "size")).reset_index()
    nodes = nodes[nodes.passes >= 5]
    pairs = d.groupby(["player_key", "recipient_key"]).size().rename("n").reset_index()
    pairs["a"], pairs["b"] = pairs[["player_key", "recipient_key"]].min(axis=1), pairs[["player_key", "recipient_key"]].max(axis=1)
    und = pairs.groupby(["a", "b"]).n.sum().reset_index()
    und = und[(und.n >= min_pass_pair) & und.a.isin(nodes.player_key) & und.b.isin(nodes.player_key)]
    if len(nodes) < 3 or und.empty:
        return unavailable("passing_network", "too few completed passes between players in the chosen window (needs 3+ players with 5+ passes and pairs with 3+ passes)")
    pos = nodes.set_index("player_key")
    fig = C.pitch_figure(f"{team}: passing network")
    mx = und.n.max()
    for r in und.itertuples():
        fig.add_scatter(x=[pos.x[r.a], pos.x[r.b]], y=[pos.y[r.a], pos.y[r.b]], mode="lines", line=dict(color=C.CAT[0], width=1 + 7 * r.n / mx), opacity=0.35, hovertemplate=f"{pos.passer[r.a]} ↔ {pos.passer[r.b]}: {r.n} passes<extra></extra>", showlegend=False)
    fig.add_scatter(x=nodes.x, y=nodes.y, mode="markers+text", text=[n.split()[-1] for n in nodes.passer], textposition="top center", textfont=dict(size=10, color=C.INK),
                    marker=dict(size=np.clip(nodes.passes / 2.5 + 10, 12, 36), color=C.CAT[0], line=dict(color=C.SURFACE, width=2)), customdata=np.c_[nodes.passer, nodes.passes],
                    hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} completed passes (average position of passes made)<extra></extra>", showlegend=False)
    data = und.merge(nodes[["player_key", "passer"]].rename(columns={"player_key": "a", "passer": "player_a"}), on="a").merge(nodes[["player_key", "passer"]].rename(columns={"player_key": "b", "passer": "player_b"}), on="b")
    win = f"minutes 0–{upto_minute:.0f}" if upto_minute is not None else "whole match"
    return Chart(fig, data[["player_a", "player_b", "n"]].rename(columns={"n": "passes_between"}), len(d), "wh.fact_match_events (StatsBomb passes with recipient)",
                 f"{win}; only completed passes with a recorded recipient. Node position = average location where the player's passes started (not a lineup diagram); line width = passes between the pair (both directions, ≥{min_pass_pair}); players with <5 passes omitted. Using minutes before the first substitution keeps it to the starting players.", name="passing_network")


# ------------------------------------------------------------------ home / away
def home_away(m: pd.DataFrame, country: dict) -> Chart:
    d = m[m.home_score.notna() & m.home_team_key.notna() & m.away_team_key.notna()].copy()
    if len(d) < 30:
        return unavailable("home_away", "fewer than 30 played matches in the selection")
    d["host_home"] = [country.get(h) == v for h, v in zip(d.home_team_name, d.venue_country)]
    d["host_away"] = [country.get(a) == v for a, v in zip(d.away_team_name, d.venue_country)]
    rows = []
    for comp, g in d.groupby("competition_id"):
        host = pd.concat([g[g.host_home].assign(res=lambda x: np.where(x.home_score > x.away_score, "win", np.where(x.home_score == x.away_score, "draw", "loss")), gf=lambda x: x.home_score, ga=lambda x: x.away_score),
                          g[g.host_away].assign(res=lambda x: np.where(x.away_score > x.home_score, "win", np.where(x.home_score == x.away_score, "draw", "loss")), gf=lambda x: x.away_score, ga=lambda x: x.home_score)])
        neutral = g[~g.host_home & ~g.host_away]
        for lab, x in (("Playing in own country", host), ("Neutral venue (team listed first)", neutral)):
            if x.empty:
                continue
            res = x.res if "res" in x else pd.Series(np.where(x.home_score > x.away_score, "win", np.where(x.home_score == x.away_score, "draw", "loss")))
            gf = x.gf if "gf" in x else x.home_score
            ga = x.ga if "ga" in x else x.away_score
            rows.append(dict(competition_id=comp, context=lab, n=len(x), win_pct=100 * (res == "win").mean(), draw_pct=100 * (res == "draw").mean(), loss_pct=100 * (res == "loss").mean(), goals_for=gf.mean(), goals_against=ga.mean()))
    t = pd.DataFrame(rows)
    t = t[t.n >= 8]
    if t.empty:
        return unavailable("home_away", "no competition has 8+ matches in either context in the selection")
    t["label"] = t.competition_id.map(C.COMP_LABEL) + "<br>" + t.context.str.replace(" (team listed first)", "") + "<br>n=" + t.n.astype(str)
    fig = go.Figure()
    for col, lab, color in (("win_pct", "Win", C.OUTCOME_COLOR["win"]), ("draw_pct", "Draw", C.OUTCOME_COLOR["draw"]), ("loss_pct", "Loss", C.OUTCOME_COLOR["loss"])):
        fig.add_bar(x=t.label, y=t[col], name=lab, marker_color=color, hovertemplate="%{x}<br>" + lab + ": %{y:.1f}%<extra></extra>")
    fig.update_layout(barmode="stack")
    C.style(fig, "Playing at home vs neutral ground: result shares", None, "Share of matches (%)", height=460)
    C.bar_gap(fig)
    fig.update_xaxes(tickfont=dict(size=10))
    return Chart(fig, t.drop(columns="label").round(2), int(t.n.sum()), SRC, "'Own country' = the team's country equals the venue's country (hosts, and every Nations League home match). On neutral ground the two sides are just 'listed first / second': no home advantage exists there. Hosts are also usually stronger/seeded, so this is an association.", name="home_away")


# ------------------------------------------------------------------ penalty shootouts
def shootouts(m: pd.DataFrame) -> tuple[Chart, Chart, Chart]:
    s = m[m.had_shootout].copy()
    if s.empty:
        u = unavailable("shootouts", "no penalty shoot-outs in the selection")
        return u, u, u
    s["winner"] = np.where(s.shootout_winner_side == "home", s.home_team_name, np.where(s.shootout_winner_side == "away", s.away_team_name, None))
    s["loser"] = np.where(s.shootout_winner_side == "home", s.away_team_name, np.where(s.shootout_winner_side == "away", s.home_team_name, None))
    per = s.groupby(["season_id", "competition_id"]).size().rename("shootouts").reset_index().sort_values(["competition_id", "season_id"])
    f1 = go.Figure()
    for c in C.COMPS:
        x = per[per.competition_id == c]
        if len(x):
            f1.add_bar(x=x.season_id, y=x.shootouts, name=C.COMP_LABEL[c], marker_color=C.COMP_COLOR[c], hovertemplate="%{x}: %{y} shoot-out(s)<extra></extra>")
    C.style(f1, "Penalty shoot-outs per edition", "Edition", "Shoot-outs (count)", height=380)
    C.bar_gap(f1)
    f1.update_xaxes(tickangle=60)
    f1.update_yaxes(dtick=1)
    c1 = Chart(f1, per, len(s), SRC, "Counts shoot-outs recorded in the data. Nations League extra time/penalties may be under-recorded; 0 = none occurred in the recorded matches.", name="shootouts_by_edition")
    # scores
    sc = s.dropna(subset=["home_pen", "away_pen"])
    if len(sc) >= 5:
        f2 = go.Figure()
        agg = sc.groupby(["home_pen", "away_pen"]).size().rename("n").reset_index()
        agg["w"], agg["l"] = agg[["home_pen", "away_pen"]].max(axis=1), agg[["home_pen", "away_pen"]].min(axis=1)
        a2 = agg.groupby(["w", "l"]).n.sum().reset_index()
        f2.add_scatter(x=a2.l, y=a2.w, mode="markers+text", text=a2.n, textposition="middle center", textfont=dict(color="#ffffff", size=11), marker=dict(size=np.clip(18 + 10 * a2.n, 22, 48), color=C.CAT[0], line=dict(color=C.SURFACE, width=2)),
                       hovertemplate="winner %{y} – loser %{x}<br>%{text} shoot-out(s)<extra></extra>", showlegend=False)
        C.style(f2, "Shoot-out scores (winner vs loser)", "Loser's penalties scored", "Winner's penalties scored", legend=False, height=380)
        f2.update_xaxes(dtick=1); f2.update_yaxes(dtick=1)
        c2 = Chart(f2, a2, len(sc), SRC, f"Kick scores are known for {len(sc)} of {len(s)} shoot-outs (the others only have the winner): missing, not 0–0. Number in the bubble = count; includes sudden death.", name="shootout_scores")
    else:
        c2 = unavailable("shootout_scores", "fewer than 5 shoot-outs with recorded kick scores in the selection")
    # team records with Wilson CI
    r = pd.concat([s.dropna(subset=["winner"]).winner.rename("team").to_frame().assign(w=1), s.dropna(subset=["loser"]).loser.rename("team").to_frame().assign(w=0)]).groupby("team").w.agg(["sum", "count"]).reset_index()
    r = r[r["count"] >= 3].copy()
    if len(r) < 3:
        c3 = unavailable("shootout_records", "fewer than 3 teams with 3+ shoot-outs in the selection")
    else:
        ci = [C.wilson(int(k), int(n)) for k, n in zip(r["sum"], r["count"])]
        r["rate"], r["lo"], r["hi"] = r["sum"] / r["count"], [a for a, _ in ci], [b for _, b in ci]
        r = r.sort_values("rate")
        f3 = go.Figure(go.Scatter(x=100 * r.rate, y=r.team + " (" + r["sum"].astype(int).astype(str) + "/" + r["count"].astype(int).astype(str) + ")", mode="markers", marker=dict(size=10, color=C.CAT[0], line=dict(color=C.SURFACE, width=2)),
                                  error_x=dict(type="data", symmetric=False, array=100 * (r.hi - r.rate), arrayminus=100 * (r.rate - r.lo), color=C.INK2, thickness=1.3, width=4),
                                  hovertemplate="%{y}<br>win rate %{x:.0f}% (95% Wilson CI shown)<extra></extra>"))
        f3.add_vline(x=50, line=dict(color=C.AXIS, width=1))
        C.style(f3, "Shoot-out win rate by team (3+ shoot-outs)", "Shoot-outs won (%) with 95% Wilson interval", None, legend=False, height=max(320, 28 * len(r) + 140))
        c3 = Chart(f3, r.rename(columns={"sum": "won", "count": "shootouts"}).round(3), int(r["count"].sum()), SRC, "Every interval includes 50% except in rare cases: with so few shoot-outs per team, the data do not show any team to be reliably better or worse.", name="shootout_records")
    return c1, c2, c3
