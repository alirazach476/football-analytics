"""ML projects 3 and 4: team clustering and (position-aware) player clustering.

Rules from the spec: standardise, choose k with silhouette, profile clusters, and name a cluster ONLY after its centroid has been
examined - names here are produced by explicit rules over the standardised centroid values and the profile table is saved next to them.
Possession is not available in this dataset and is therefore not used. Clustering is unsupervised: clusters are descriptions, not truths."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cophenet, fcluster, linkage
from scipy.spatial.distance import pdist
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from ..analysis import data as D
from . import tracking as T

warnings.filterwarnings("ignore")
SEED = 42
TEAM_FEATURES = ["gf_pm", "ga_pm", "win_pct", "ppm", "gd_pm", "clean_sheet_pct", "goals_sd", "ppm_sd_editions"]


def team_table(min_matches=15) -> pd.DataFrame:
    tm = D.team_matches()
    g = tm.groupby("team_name").agg(matches=("match_key", "size"), gf_pm=("goals_for", "mean"), ga_pm=("goals_against", "mean"), ppm=("points", "mean"),
                                    win_pct=("result", lambda s: 100 * (s == "W").mean()), clean_sheet_pct=("clean_sheet", lambda s: 100 * s.mean()),
                                    goals_sd=("goal_diff", "std"), editions=("season_id", "nunique")).reset_index()
    ed = tm.groupby(["team_name", "season_id"]).points.mean().groupby("team_name").std().rename("ppm_sd_editions")
    g = g.merge(ed, on="team_name", how="left")
    g["gd_pm"] = g.gf_pm - g.ga_pm
    g = g[g.matches >= min_matches].dropna(subset=TEAM_FEATURES).reset_index(drop=True)
    return g


def _best_k(Z, ks=range(2, 9)):
    sc = {k: silhouette_score(Z, KMeans(k, n_init=20, random_state=SEED).fit_predict(Z)) for k in ks}
    return max(sc, key=sc.get), sc


def _stability(Z, k, b=40):
    base = KMeans(k, n_init=20, random_state=SEED).fit_predict(Z)
    rng = np.random.default_rng(SEED)
    aris = []
    for _ in range(b):
        i = rng.choice(len(Z), len(Z), replace=True)
        lab = KMeans(k, n_init=10, random_state=int(rng.integers(1e6))).fit(Z[i]).predict(Z)
        aris.append(adjusted_rand_score(base, lab))
    return float(np.mean(aris)), float(np.percentile(aris, 5))


def name_team_cluster(z: pd.Series) -> str:
    """Rule-based description from the standardised centroid (z-scores of the cluster mean)."""
    att, dfn, var = z["gf_pm"], -z["ga_pm"], z["goals_sd"]
    if att > 0.7 and dfn > 0.7:
        return "dominant: strong attack and strong defence"
    if att > 0.5 and dfn <= 0.5:
        return "attack-led"
    if dfn > 0.5 and att <= 0.5:
        return "defence-led"
    if att < -0.5 and dfn < -0.5:
        return "weak at both ends"
    if att < -0.5:
        return "low-scoring"
    return "balanced / mid-table"


def cluster_teams(track=True):
    t = team_table()
    Z = StandardScaler().fit_transform(t[TEAM_FEATURES])
    k, sil = _best_k(Z)
    km = KMeans(k, n_init=50, random_state=SEED).fit(Z)
    t["kmeans"] = km.labels_
    link = linkage(Z, "ward")
    coph = float(cophenet(link, pdist(Z))[0])
    t["hierarchical"] = fcluster(link, k, "maxclust") - 1
    best = (None, -1)
    for eps in np.arange(0.6, 2.6, 0.1):
        for ms in (3, 4, 5):
            lab = DBSCAN(eps=eps, min_samples=ms).fit_predict(Z)
            n_cl = len(set(lab)) - (1 if -1 in lab else 0)
            if n_cl >= 2 and (lab == -1).mean() <= 0.3:
                s = silhouette_score(Z[lab != -1], lab[lab != -1])
                if s > best[1]:
                    best = ((eps, ms), s)
    if best[0]:
        t["dbscan"] = DBSCAN(eps=best[0][0], min_samples=best[0][1]).fit_predict(Z)
    else:
        t["dbscan"] = -1
    stab = _stability(Z, k)
    prof = pd.DataFrame(Z, columns=TEAM_FEATURES).assign(cluster=t.kmeans).groupby("cluster")[TEAM_FEATURES].mean()
    raw = t.groupby("kmeans")[TEAM_FEATURES + ["matches"]].mean().round(3)
    raw["n_teams"] = t.groupby("kmeans").size()
    raw["suggested_description"] = [name_team_cluster(prof.loc[c]) for c in raw.index]
    raw["members"] = [", ".join(t[t.kmeans == c].sort_values("matches", ascending=False).team_name.head(12)) for c in raw.index]
    t["cluster_description"] = t.kmeans.map(raw.suggested_description)
    summary = pd.DataFrame([dict(
        k_selected=k, silhouette_kmeans=sil[k], silhouette_by_k=str({kk: round(v, 3) for kk, v in sil.items()}), cophenetic_correlation_ward=coph,
        silhouette_hierarchical=silhouette_score(Z, t.hierarchical) if t.hierarchical.nunique() > 1 else np.nan,
        dbscan_params=str(best[0]), dbscan_silhouette_non_noise=best[1] if best[0] else np.nan, dbscan_clusters=int(len(set(t.dbscan)) - (1 if -1 in set(t.dbscan) else 0)),
        dbscan_noise_teams=int((t.dbscan == -1).sum()), ari_kmeans_vs_hierarchical=adjusted_rand_score(t.kmeans, t.hierarchical),
        ari_kmeans_vs_dbscan=adjusted_rand_score(t.kmeans, t.dbscan), bootstrap_stability_mean_ari=stab[0], bootstrap_stability_p05_ari=stab[1], n_teams=len(t),
        features=",".join(TEAM_FEATURES), note="possession not available in the dataset; min 15 matches per team")])
    # exploratory finer split (k=4) to look for the spec's suggested categories; NOT the selected model (lower silhouette)
    k4 = KMeans(4, n_init=50, random_state=SEED).fit(Z)
    p4 = pd.DataFrame(Z, columns=TEAM_FEATURES).assign(cluster=k4.labels_).groupby("cluster")[TEAM_FEATURES].mean()
    r4 = t.assign(k4=k4.labels_).groupby("k4")[TEAM_FEATURES + ["matches"]].mean().round(3)
    r4["n_teams"] = t.assign(k4=k4.labels_).groupby("k4").size()
    r4["suggested_description"] = [name_team_cluster(p4.loc[c]) for c in r4.index]
    r4["silhouette_k4"] = silhouette_score(Z, k4.labels_)
    r4["members"] = [", ".join(t[k4.labels_ == c].sort_values("matches", ascending=False).team_name.head(10)) for c in r4.index]
    T.save_table(r4.reset_index(), "team_cluster_profiles_k4_exploratory", "clustering")
    T.save_table(t, "team_clusters", "clustering")
    T.save_table(raw.reset_index(), "team_cluster_profiles", "clustering")
    T.save_table(summary, "team_clustering_summary", "clustering")
    if track:
        import mlflow
        with T.run("team_clustering", "kmeans+ward+dbscan", params=dict(k=k, features=len(TEAM_FEATURES), teams=len(t))):
            T.log_metrics({"silhouette_kmeans": sil[k], "cophenetic": coph, "stability_ari": stab[0]})
            mlflow.log_artifact(str(T.REPORTS / "clustering" / "team_cluster_profiles.csv"))
    return dict(teams=t, profiles=raw, summary=summary)


# ------------------------------------------------------------------ players
PLAYER_FEATS = ["goals_p90", "xg_p90", "shots_p90", "assists_p90", "xa_p90", "key_passes_p90", "passes_p90", "pass_acc", "tackles_p90", "interceptions_p90",
                "clearances_p90", "blocks_p90", "fouls_committed_p90"]
POS_ORDER = ["Defender", "Midfielder", "Forward"]


def pos_group(p):
    if not isinstance(p, str):
        return None
    pl = p.lower()
    if "goalkeeper" in pl:
        return "Goalkeeper"
    if any(w in pl for w in ("forward", "striker", "wing", "second striker")) and "back" not in pl:
        return "Forward"
    if "midfield" in pl:
        return "Midfielder"
    if "back" in pl or "defen" in pl or "sweeper" in pl:
        return "Defender"
    return "Other"


def player_stat_table(min_minutes=270) -> pd.DataFrame:
    s = D.q("""select ps.player_key, d.full_name, d.primary_position, sum(ps.minutes_played) mins, count(*) matches,
                      sum(goals) goals, sum(assists) assists, sum(shots) shots, sum(xg) xg, sum(xa) xa, sum(key_passes) key_passes, sum(passes) passes,
                      sum(passes_completed) passes_completed, sum(tackles) tackles, sum(interceptions) interceptions, sum(clearances) clearances,
                      sum(blocks) blocks, sum(fouls_committed) fouls_committed, sum(saves) saves
               from wh.fact_player_match_stats ps join wh.dim_player d using (player_key)
               where ps.minutes_played is not null group by 1, 2, 3""")
    for c in s.columns[3:]:
        s[c] = pd.to_numeric(s[c], errors="coerce")
    s = s[s.mins >= min_minutes].copy()
    s["position"] = s.primary_position.map(pos_group)
    for c in ("goals", "xg", "shots", "assists", "xa", "key_passes", "passes", "tackles", "interceptions", "clearances", "blocks", "fouls_committed", "saves"):
        s[f"{c}_p90"] = 90 * s[c] / s.mins
    s["pass_acc"] = s.passes_completed / s.passes.replace(0, np.nan)
    return s


def name_player_cluster(pos: str, z: pd.Series) -> str:
    top = z.sort_values(ascending=False)
    hi = [f for f in top.index if top[f] > 0.6][:3]
    if not hi:
        return f"{pos}: average profile"
    nice = {"goals_p90": "scoring", "xg_p90": "chance-taking", "shots_p90": "shooting", "assists_p90": "assisting", "xa_p90": "chance-creating", "key_passes_p90": "key passing",
            "passes_p90": "high-volume passing", "pass_acc": "secure passing", "tackles_p90": "tackling", "interceptions_p90": "intercepting", "clearances_p90": "clearing",
            "blocks_p90": "blocking", "fouls_committed_p90": "physical (fouls)"}
    return f"{pos}: " + ", ".join(nice[f] for f in hi)


def cluster_players(track=True):
    s = player_stat_table()
    out, profiles, summ = [], [], []
    for pos in POS_ORDER:
        g = s[s.position == pos].dropna(subset=PLAYER_FEATS).copy()
        if len(g) < 40:
            continue
        Z = StandardScaler().fit_transform(g[PLAYER_FEATS])
        k, sil = _best_k(Z, range(2, 6))
        g["cluster"] = KMeans(k, n_init=30, random_state=SEED).fit_predict(Z)
        stab = _stability(Z, k, b=25)
        zc = pd.DataFrame(Z, columns=PLAYER_FEATS, index=g.index).assign(cluster=g.cluster).groupby("cluster")[PLAYER_FEATS].mean()
        g["cluster_description"] = g.cluster.map({c: name_player_cluster(pos, zc.loc[c]) for c in zc.index})
        prof = g.groupby("cluster")[PLAYER_FEATS + ["mins"]].mean().round(3)
        prof["n_players"] = g.groupby("cluster").size()
        prof["position"] = pos
        prof["description"] = [name_player_cluster(pos, zc.loc[c]) for c in prof.index]
        prof["examples"] = [", ".join(g[g.cluster == c].sort_values("mins", ascending=False).full_name.head(6)) for c in prof.index]
        profiles.append(prof.reset_index())
        summ.append(dict(position=pos, n_players=len(g), k=k, silhouette=sil[k], silhouette_by_k=str({kk: round(v, 3) for kk, v in sil.items()}), bootstrap_stability_mean_ari=stab[0]))
        out.append(g[["player_key", "full_name", "position", "mins", "cluster", "cluster_description"]])
    gk = s[s.position == "Goalkeeper"][["player_key", "full_name", "mins", "matches", "saves", "saves_p90", "passes_p90", "pass_acc", "clearances_p90"]].sort_values("mins", ascending=False)
    allc = pd.concat(out, ignore_index=True)
    T.save_table(allc, "player_clusters_by_position", "clustering")
    T.save_table(pd.concat(profiles, ignore_index=True), "player_cluster_profiles", "clustering")
    T.save_table(pd.DataFrame(summ).assign(note="clustered WITHIN position; features per 90 from StatsBomb-covered matches only; goalkeepers not clustered (too few, different role) - see goalkeeper table"), "player_clustering_summary", "clustering")
    T.save_table(gk, "goalkeeper_profiles", "clustering")
    if track:
        import mlflow
        with T.run("player_clustering", "kmeans_by_position", params=dict(features=len(PLAYER_FEATS), min_minutes=270)):
            for r in summ:
                T.log_metrics({f"silhouette_{r['position']}": r["silhouette"]})
    return dict(players=allc, profiles=pd.concat(profiles, ignore_index=True), summary=pd.DataFrame(summ), goalkeepers=gk, stats=s)


if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 70)
    t = cluster_teams()
    print(t["summary"].T.to_string()); print(t["profiles"][["n_teams", "gf_pm", "ga_pm", "win_pct", "suggested_description", "members"]].to_string())
    p = cluster_players()
    print(p["summary"].to_string()); print(p["profiles"][["position", "cluster", "n_players", "goals_p90", "assists_p90", "tackles_p90", "description", "examples"]].to_string())
