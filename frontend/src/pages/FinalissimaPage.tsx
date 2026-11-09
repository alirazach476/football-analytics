import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { CalendarClock, ExternalLink, MapPin, Trophy, Users } from "lucide-react";
import { Table } from "../api";
import { themeFor } from "../theme/editions";
import { Callout, Section, Skeleton, Tabs } from "../components/ui";
import { BODY_OF } from "../components/Brand";
import CountryFlag from "../components/CountryFlag";
import MatchScoreboard, { TimelineEvt } from "../components/match/MatchScoreboard";
import MatchTimeline from "../components/match/MatchTimeline";
import StatisticsComparison, { statRows } from "../components/match/StatisticsComparison";
import TeamLineup, { Manager, Player } from "../components/match/FootballPitch";
import { MatchRow, dateLabel } from "../components/match/matchUtils";

interface Edition {
  seasonId: string; slug: string; edition: string; year: number; host: string; start: string; teams: number; format: string; status: string; cancelled: boolean; champion: string | null; runnerUp: string | null;
  match: MatchRow; kickoff: string | null; officials: Record<string, string>; managers: { home?: Manager; away?: Manager }; timeline: TimelineEvt[]; teamStats: Record<string, any>[]; lineups: Player[];
  sources: { label: string; url: string }[]; notes: string[];
}

/** CONMEBOL–UEFA Cup of Champions: a curated, sourced section (2022 played, 2026 cancelled). Same broadcast components as the Match Center, with only what the sources state. */
export default function FinalissimaPage({ slug }: { slug: string }) {
  const q = useQuery({ queryKey: ["finalissima"], queryFn: async () => { const r = await fetch("/api/finalissima"); if (!r.ok) throw new Error(r.statusText); return (await r.json()) as { editions: Edition[] }; }, staleTime: 3_600_000 });
  const [tab, setTab] = useState("Overview"); const theme = themeFor(slug);
  const all = q.data?.editions ?? []; const e = all.find((x) => x.slug === slug);
  if (q.isError || (q.data && !e)) return <Navigate to="/competition/fin" replace />;
  if (!e) return <Skeleton h={520} />;
  const m = e.match; const played = m.is_played; const stats: Table = { columns: ["team_name"], rows: e.teamStats, total: e.teamStats.length };
  const hasStats = statRows(stats, m.home_team_name, m.away_team_name).length > 0;
  const tabs = ["Overview", ...(hasStats ? ["Statistics"] : []), ...(e.lineups.length ? ["Lineups"] : []), ...(e.timeline.length ? ["Events"] : []), "Details & sources"];
  const cur = tabs.includes(tab) ? tab : "Overview"; const other = all.find((x) => x.slug !== slug);
  return (
    <div>
      <Link to="/competition/fin" className="mb-3 inline-block text-sm font-semibold" style={{ color: "var(--c-primary)" }}>← Finalissima</Link>
      <section className="hero mb-8 text-white" style={{ background: `linear-gradient(120deg, ${theme.heroFrom}, ${theme.heroTo})`, minHeight: 380, boxShadow: `0 40px 90px -45px ${theme.primary}` }}>
        <div className="pattern-rings absolute inset-0 -z-10 opacity-60" />
        <div className="absolute inset-0 -z-10" style={{ background: `radial-gradient(70% 90% at 12% 60%, color-mix(in srgb, ${theme.primary} 40%, transparent), transparent 70%)` }} />
        <div className="ghost-text absolute -bottom-4 right-4 -z-10 hidden text-[15vw] md:block" aria-hidden>{e.year}</div>
        <div className="absolute right-4 top-4 flex gap-2">{BODY_OF.FIN.map((b) => <img key={b.id} src={b.logo} alt={`${b.name} logo`} className="h-10 rounded-lg bg-white p-1 object-contain shadow-lg" />)}</div>
        <div className="flex flex-wrap items-center gap-8 p-6 sm:p-12">
          <motion.img initial={{ scale: 0.7, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} src={theme.logo} alt={`${e.edition} logo`} className="glow-logo h-44 w-44 rounded-3xl object-contain sm:h-60 sm:w-60" />
          <div className="min-w-0 flex-1">
            <span className="inline-block px-3 py-1 text-xs font-bold uppercase tracking-[0.24em]" style={{ background: theme.primary, color: "var(--c-on-primary)", clipPath: "polygon(0 0,100% 0,94% 100%,0 100%)" }}>CONMEBOL–UEFA Cup of Champions</span>
            <h1 className="display-caps mt-3 text-5xl font-extrabold leading-[.95] sm:text-7xl">Finalissima<span className="block" style={{ color: theme.accent }}>{e.year}</span></h1>
            <p className="mt-3 max-w-2xl text-base font-medium opacity-90 sm:text-lg">{theme.tagline}</p>
            <div className="mt-5 flex flex-wrap gap-2 text-xs font-bold uppercase tracking-wider">
              {e.cancelled && <span className="chip chip-soon !text-sm"><CalendarClock size={14} />Cancelled</span>}
              <span className="bc-slant bg-white/15 px-4 py-1.5 backdrop-blur"><MapPin size={12} className="mr-1 inline" />{e.host}</span>
              <span className="bc-slant bg-white/15 px-4 py-1.5 backdrop-blur">{dateLabel(e.start, { day: "numeric", month: "long", year: "numeric" })}{e.kickoff ? ` · ${e.kickoff}` : ""}</span>
              <span className="bc-slant bg-white/15 px-4 py-1.5 backdrop-blur"><Users size={12} className="mr-1 inline" />{m.home_team_name} v {m.away_team_name}</span>
            </div>
          </div>
          {e.champion && <div className="px-8 py-6 text-center text-slate-900 shadow-2xl" style={{ background: "linear-gradient(145deg,#fde68a,#f59e0b)", borderRadius: "var(--r)" }}>
            <Trophy className="mx-auto mb-1" size={34} /><div className="text-[11px] font-extrabold uppercase tracking-[0.3em]">Winner</div>
            <div className="mt-1 flex items-center justify-center gap-2 font-display text-3xl font-extrabold uppercase"><CountryFlag country={e.champion} size={34} />{e.champion}</div>
            {e.runnerUp && <div className="mt-1 flex items-center justify-center gap-1.5 text-xs font-semibold opacity-80">beat <CountryFlag country={e.runnerUp} size={18} />{e.runnerUp}</div>}</div>}
        </div>
      </section>

      {e.cancelled && <Callout tone="warn" title="This match was cancelled" className="mb-6">{m.fixture_detail} There is no result, line-up or statistics, and nothing is estimated.</Callout>}
      <MatchScoreboard match={m} events={e.timeline} theme={theme} goalsComplete={played ? true : undefined} />
      <div className="mt-5"><Tabs tabs={tabs} value={cur} onChange={setTab} id="fin" /></div>
      <div className="pt-6">
        {cur === "Overview" && <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
          <div className="space-y-6">
            <div className="card p-5"><h3 className="mb-3 font-display font-bold">Summary</h3><ul className="space-y-1.5 text-sm">
              {played ? <li><b>{m.home_team_name} {m.home_score}–{m.away_score} {m.away_team_name}</b> · half-time {m.home_score_ht}–{m.away_score_ht}</li> : <li><b>{m.home_team_name} v {m.away_team_name}</b>: cancelled, no result.</li>}
              <li>{dateLabel(m.match_date, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}{e.kickoff ? ` · kick-off ${e.kickoff}` : ""}</li>
              <li>{[m.venue_name, m.venue_city, m.venue_country].filter(Boolean).join(", ")}{m.attendance ? ` · attendance ${Number(m.attendance).toLocaleString()}` : ""}</li>
              {m.man_of_the_match_raw && <li>Man of the match: <b>{m.man_of_the_match_raw}</b></li>}
              {(e.managers.home || e.managers.away) && <li>Managers: <b>{e.managers.home?.name}</b> ({m.home_team_name}) · <b>{e.managers.away?.name}</b> ({m.away_team_name})</li>}
              <li>Format: {e.format}</li></ul></div>
            {hasStats && <StatisticsComparison stats={stats} home={m.home_team_name} away={m.away_team_name} />}
          </div>
          <div>{e.timeline.length > 0 ? <MatchTimeline events={e.timeline.filter((x) => x.kind !== "Substitution")} match={m} /> : <Callout tone="info">No events: the match was not played.</Callout>}</div>
        </div>}
        {cur === "Statistics" && <StatisticsComparison stats={stats} home={m.home_team_name} away={m.away_team_name} />}
        {cur === "Lineups" && <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
          <TeamLineup team={m.home_team_name} players={e.lineups.filter((p) => p.team_name === m.home_team_name)} manager={e.managers.home} />
          <TeamLineup team={m.away_team_name} players={e.lineups.filter((p) => p.team_name === m.away_team_name)} manager={e.managers.away} /></div>}
        {cur === "Events" && <MatchTimeline events={e.timeline} match={m} />}
        {cur === "Details & sources" && <div className="space-y-6">
          {Object.keys(e.officials).length > 0 && <Section title="Match officials"><div className="card divide-y p-0" style={{ borderColor: "var(--c-border)" }}>{Object.entries(e.officials).map(([k, v]) => <div key={k} className="grid gap-1 p-3 sm:grid-cols-[11rem_1fr]" style={{ borderColor: "var(--c-border)" }}><span className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--c-primary)" }}>{k}</span><span className="text-sm">{v}</span></div>)}</div></Section>}
          <Section title="Notes"><ul className="space-y-2 text-sm">{e.notes.map((n) => <li key={n} className="card p-3">{n}</li>)}</ul></Section>
          <Section title="Sources"><ul className="space-y-1.5 text-sm">{e.sources.map((s) => <li key={s.url}><a className="inline-flex items-center gap-1.5 font-medium hover:underline" style={{ color: "var(--c-primary)" }} href={s.url} target="_blank" rel="noreferrer">{s.label}<ExternalLink size={12} /></a></li>)}</ul></Section>
          <Callout tone="info" title="A separate section">The Finalissima is not one of the four competitions of the warehouse, so it is not part of the platform's statistics, models or counts.</Callout>
        </div>}
        {other && <p className="mt-8 text-sm"><Link to={`/tournament/${other.slug}`} className="font-semibold" style={{ color: "var(--c-primary)" }}>Also see the {other.edition} →</Link></p>}
      </div>
    </div>
  );
}
