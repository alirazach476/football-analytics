import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Table } from "../api";
import { themeFor } from "../theme/editions";
import { useThemeOverride } from "../theme/useTheme";
import { Callout, Skeleton, Tabs } from "../components/ui";
import ChartSection from "../components/ChartSection";
import QuickPlot from "../components/QuickPlot";
import MatchScoreboard, { TimelineEvt } from "../components/match/MatchScoreboard";
import MatchTimeline from "../components/match/MatchTimeline";
import StatisticsComparison, { METRICS, statRows } from "../components/match/StatisticsComparison";
import TeamLineup, { playersOf } from "../components/match/FootballPitch";
import HeadToHead from "../components/match/HeadToHead";
import { MatchRow, dateLabel } from "../components/match/matchUtils";

interface Center { match: MatchRow; timeline: Table; teamStats: Table; lineups: Table; headToHead: Table; goalsComplete: boolean; hasCommentary: boolean; managers: { home?: { name: string; source: string; level: string }; away?: { name: string; source: string; level: string } }; assistsRecorded: boolean }

export function MatchCenterView({ matchKey, embedded = false }: { matchKey: string | number; embedded?: boolean }) {
  const key = String(matchKey); const [tab, setTab] = useState("Overview");
  const q = useQuery({ queryKey: ["match-center", key], queryFn: async () => { const r = await fetch(`/api/match-center/${key}`); if (!r.ok) throw new Error((await r.json().catch(() => ({ error: { message: r.statusText } }))).error?.message ?? r.statusText); return (await r.json()) as Center; }, staleTime: 300_000 });
  const d = q.data; const m = d?.match; useThemeOverride(m?.season_id);
  const theme = themeFor(m?.season_id ?? "app");
  const events = (d?.timeline.rows ?? []) as TimelineEvt[];
  const stats = useMemo(() => (d ? statRows(d.teamStats, m!.home_team_name, m!.away_team_name) : []), [d, m]);
  if (q.isError) return <Callout tone="warn" title="Match not found">{(q.error as Error).message} <Link to="/fixtures" className="underline">Back to fixtures</Link></Callout>;
  if (!d || !m) return <div className="space-y-4"><Skeleton h={340} /><Skeleton h={200} /></div>;
  const played = m.is_played && m.home_score != null;
  const tabs = ["Overview", ...(stats.length ? ["Statistics"] : []), ...(d.lineups.rows.length ? ["Lineups"] : []), ...(events.length ? ["Events"] : []), ...(d.hasCommentary ? ["Commentary"] : []), "Head-to-Head"];
  const cur = tabs.includes(tab) ? tab : "Overview";
  const half = played && m.home_score_ht != null && m.home_score_ft90 != null;
  const maxOf = (k: string) => { const r = d.teamStats.rows; return Math.max(...r.map((x) => Number(x[k]) || 0)) || 1; };
  const radarM = METRICS.filter((x) => ["shots", "shots_on_target", "passes", "pass_accuracy", "corners_taken", "xg"].includes(x.key) && stats.some((s) => s.m.key === x.key));
  const hs = d.teamStats.rows.find((r) => r.team_name === m.home_team_name), as = d.teamStats.rows.find((r) => r.team_name === m.away_team_name);
  const keyEvents = events.filter((e) => e.kind !== "Substitution");
  return (
    <div>
      {!embedded && <Link to="/fixtures" className="mb-3 inline-flex items-center gap-1.5 text-sm font-semibold" style={{ color: "var(--c-primary)" }}><ArrowLeft size={15} />Fixtures &amp; results</Link>}
      <MatchScoreboard match={m} events={events} theme={theme} goalsComplete={played ? d.goalsComplete : undefined} />
      <div className="mt-5"><Tabs tabs={tabs} value={cur} onChange={setTab} id="mc" /></div>
      <div className="pt-6">
        {cur === "Overview" && <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
          <div className="space-y-6">
            <div className="card p-5"><h3 className="mb-3 font-display font-bold">Match summary</h3>
              {!played ? <p className="text-sm"><b>Coming soon.</b> {m.fixture_detail ?? "No result exists yet."} No statistics or events exist until the match is played.</p> : <ul className="space-y-1.5 text-sm">
                <li><b>{m.home_team_name} {m.home_score}–{m.away_score} {m.away_team_name}</b>{m.went_beyond_90 ? " after extra time" : ""}{m.had_shootout && m.home_pen != null ? `; ${m.shootout_winner_side === "home" ? m.home_team_name : m.away_team_name} won ${Math.max(m.home_pen, m.away_pen!)}–${Math.min(m.home_pen, m.away_pen!)} on penalties` : ""}.</li>
                {m.home_score_ht != null && <li>Half-time: {m.home_score_ht}–{m.away_score_ht}{m.went_beyond_90 && m.home_score_ft90 != null ? ` · after 90 minutes: ${m.home_score_ft90}–${m.away_score_ft90}` : ""}</li>}
                {(d.managers.home || d.managers.away) && <li>Managers: <b>{d.managers.home?.name ?? "n/a"}</b> ({m.home_team_name}) · <b>{d.managers.away?.name ?? "n/a"}</b> ({m.away_team_name})</li>}
                {played && events.some((e) => e.kind === "Goal") && !d.assistsRecorded && <li style={{ color: "var(--c-muted)" }}>Assists are not recorded for this match by its sources.</li>}
                {m.man_of_the_match_raw && <li>Player of the match: <b>{m.man_of_the_match_raw}</b></li>}
                <li>{dateLabel(m.match_date, { weekday: "long", day: "numeric", month: "long", year: "numeric" })} · {m.stage_name}{m.group_name ? ` · Group ${m.group_name}` : ""}</li>
                <li>{[m.venue_name, m.venue_city, m.venue_country].filter(Boolean).join(", ") || "Venue to be confirmed"}{m.attendance ? ` · attendance ${Number(m.attendance).toLocaleString()}` : ""}{m.referee_name ? ` · referee ${m.referee_name}` : ""}</li></ul>}
            </div>
            {stats.length > 0 && <StatisticsComparison stats={d.teamStats} home={m.home_team_name} away={m.away_team_name} />}
          </div>
          <div>{keyEvents.length > 0 ? <MatchTimeline events={keyEvents} match={m} /> : played ? <Callout tone="info">No minute-level events are recorded for this match (the sources have none).</Callout> : null}</div>
        </div>}

        {cur === "Statistics" && <div className="space-y-6">
          <StatisticsComparison stats={d.teamStats} home={m.home_team_name} away={m.away_team_name} />
          <div className="grid gap-6 xl:grid-cols-2 [&>*]:min-w-0">
            {radarM.length >= 3 && hs && as && <QuickPlot height={380} data={[m.home_team_name, m.away_team_name].map((t, i) => { const r = i ? as : hs; return { type: "scatterpolar", fill: "toself", name: t, r: [...radarM, radarM[0]].map((x) => (Number(r[x.key]) || 0) / maxOf(x.key)), theta: [...radarM, radarM[0]].map((x) => x.label),
              customdata: [...radarM, radarM[0]].map((x) => (x.pct ? `${Math.round(r[x.key] * 100)}%` : Number(r[x.key]).toFixed(x.dec ?? 0))), hovertemplate: "%{theta}: %{customdata}<extra>" + t + "</extra>", opacity: 0.6 }; })}
              layout={{ title: { text: "Team performance radar" }, margin: { l: 90, r: 90, t: 70, b: 50 }, polar: { radialaxis: { visible: true, range: [0, 1], tickvals: [0.5, 1], ticktext: ["", "max"] } } }} caption="Each axis is scaled to the larger of the two teams for that metric (hover shows the real value). Only metrics recorded for this match are drawn." />}
            {half && <QuickPlot height={380} data={[{ name: "First half", type: "bar", x: [m.home_team_name, m.away_team_name], y: [m.home_score_ht, m.away_score_ht], marker: { color: "#2a78d6" }, text: [m.home_score_ht, m.away_score_ht], textposition: "outside" },
              { name: "Second half (to 90′)", type: "bar", x: [m.home_team_name, m.away_team_name], y: [m.home_score_ft90! - m.home_score_ht!, m.away_score_ft90! - m.away_score_ht!], marker: { color: "#d9822b" }, text: [m.home_score_ft90! - m.home_score_ht!, m.away_score_ft90! - m.away_score_ht!], textposition: "outside" }]}
              layout={{ title: { text: "Goals by half (regulation time)" }, barmode: "group", yaxis: { rangemode: "tozero", dtick: 1 } }} caption="From the recorded half-time and 90-minute scores. Extra-time goals are not included." />}
          </div>
          <ChartSection spec={{ id: "match.shots_match", title: "Shot map", shared: ["match_key"] }} shared={{ match_key: m.match_key }} />
        </div>}

        {cur === "Lineups" && <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
          <TeamLineup team={m.home_team_name} players={playersOf(d.lineups, m.home_team_name)} color={theme.primary} manager={d.managers.home} /><TeamLineup team={m.away_team_name} players={playersOf(d.lineups, m.away_team_name)} color={theme.secondary} manager={d.managers.away} />
          <p className="col-span-full text-xs" style={{ color: "var(--c-muted)" }}>{d.managers.home || d.managers.away ? "Managers come from StatsBomb match data or the Wikipedia match box; where only the tournament head coach is known it says so." : "No manager is recorded for this match in the sources."}</p>
        </div>}

        {cur === "Events" && <div className="space-y-6"><MatchTimeline events={events} match={m} /><ChartSection spec={{ id: "match.progress", title: "Score progression", shared: ["match_key"] }} shared={{ match_key: m.match_key }} /></div>}
        {cur === "Commentary" && <Callout tone="info">No commentary data exists.</Callout>}
        {cur === "Head-to-Head" && <HeadToHead table={d.headToHead} a={m.home_team_name} b={m.away_team_name} currentDate={m.match_date} />}
      </div>
    </div>
  );
}

export default function MatchCenter() {
  const { key = "" } = useParams();
  return <MatchCenterView key={key} matchKey={key} />;
}
