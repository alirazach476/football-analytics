import { useMemo, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { Award, CalendarClock, Flag, Goal, MapPin, Medal, Percent, Trophy, Users } from "lucide-react";
import { useTournament } from "../api";
import { themeFor } from "../theme/editions";
import { Callout, KpiCard, Section, Skeleton, Tabs } from "../components/ui";
import DataTable from "../components/DataTable";
import ChartSection from "../components/ChartSection";
import { EMPTY_FILTERS } from "../api";
import { BODY_OF } from "../components/Brand";
import CountryFlag from "../components/CountryFlag";
import FixtureCard from "../components/match/FixtureCard";
import StandingsTable from "../components/match/StandingsTable";
import Bracket from "../components/match/Bracket";
import { useQuery } from "@tanstack/react-query";

const MATCH_HIDE = ["match_key", "match_id", "is_played", "home_pen", "away_pen", "shootout_winner_side", "went_beyond_90"];

export default function TournamentPage() {
  const { slug = "" } = useParams(); const seasonId = slug.toUpperCase(); const nav = useNavigate();
  const q = useTournament(seasonId); const theme = themeFor(slug); const [tab, setTab] = useState("Overview"); const [stage, setStage] = useState("All");
  const d = q.data; const [view, setView] = useState<"cards" | "table">("cards");
  const st = useQuery({ queryKey: ["standings", seasonId], queryFn: async () => (await fetch(`/api/standings/${seasonId}`)).json(), enabled: tab === "Standings", staleTime: 300_000 });
  const filters = useMemo(() => ({ ...EMPTY_FILTERS, seasons: [seasonId] }), [seasonId]);
  const stages = useMemo(() => ["All", ...Array.from(new Set<string>((d?.matches?.rows ?? []).map((r: any) => r.stage_name).filter(Boolean)))], [d]);
  const matchTable = useMemo(() => {
    if (!d?.matches) return undefined;
    const rows = d.matches.rows.filter((r: any) => stage === "All" || r.stage_name === stage).map((r: any) => ({ ...r,
      score: r.is_played ? `${r.home_score}–${r.away_score}${r.home_pen != null ? ` (${r.home_pen}–${r.away_pen} pens)` : r.went_beyond_90 ? " (aet)" : ""}` : "–" }));
    return { columns: ["match_date", "stage_name", "group_name", "home_team_name", "score", "away_team_name", "status_label", "motm", "venue_name", "venue_city", "attendance", "referee_name", "fixture_detail", "match_key", "match_id", "is_played", "home_pen", "away_pen", "shootout_winner_side", "went_beyond_90"], rows, total: rows.length };
  }, [d, stage]);
  if (q.isError) return <Navigate to="/" replace />;
  if (!d) return <Skeleton h={500} />;
  const m = d.meta, s = d.summary ?? {}; const soon = m.status !== "in_data"; const played = m.matchesPlayed;
  const fmtDate = (x: string | null) => (x ? new Date(x).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "to be confirmed");
  const tabs = ["Overview", "Matches", "Standings", "Bracket", "Teams", "Awards", "Records", "Charts", "Coverage"];
  return (
    <div>
      <section className="hero mb-8 text-white" style={{ background: `linear-gradient(120deg, ${theme.heroFrom}, ${theme.heroTo})`, minHeight: 420, boxShadow: `0 40px 90px -45px ${theme.primary}` }}>
        {theme.banner && <motion.img initial={{ scale: 1.12 }} animate={{ scale: 1 }} transition={{ duration: 2.2, ease: "easeOut" }} src={theme.banner} alt={`${m.edition} artwork`} className="absolute inset-0 -z-20 h-full w-full object-cover saturate-125" />}
        <div className={`pattern-${theme.pattern} absolute inset-0 -z-10 opacity-70`} />
        <div className="absolute inset-0 -z-10" style={{ background: `linear-gradient(95deg, rgba(4,8,18,.88) 0%, rgba(4,8,18,.55) 48%, rgba(4,8,18,.12) 100%), radial-gradient(70% 90% at 12% 60%, color-mix(in srgb, ${theme.primary} 45%, transparent), transparent 70%)` }} />
        <div className="ghost-text absolute -bottom-4 right-4 -z-10 hidden text-[15vw] md:block" aria-hidden>{(m.competition === "UNL" ? seasonId.replace("UNL-", "") : String(m.year))}</div>
        <div className="absolute right-4 top-4 flex gap-2">{(BODY_OF[m.competition] ?? []).map((b) => <img key={b.id} src={b.logo} alt={`${b.name} logo`} className="h-10 rounded-lg bg-white p-1 object-contain shadow-lg" />)}</div>
        <div className="flex flex-wrap items-center gap-8 p-6 pb-24 sm:p-12 sm:pb-28">
          <motion.img initial={{ scale: 0.7, opacity: 0, rotate: -6 }} animate={{ scale: 1, opacity: 1, rotate: 0 }} transition={{ type: "spring", damping: 14 }} src={theme.logo} alt={`${m.edition} logo`} className="glow-logo h-44 w-44 rounded-3xl bg-white/95 object-contain p-3 sm:h-60 sm:w-60" />
          <div className="min-w-0 flex-1">
            <Link to={`/competition/${m.competition.toLowerCase()}`} className="inline-block px-3 py-1 text-xs font-bold uppercase tracking-[0.24em]" style={{ background: theme.primary, color: "var(--c-on-primary)", clipPath: "polygon(0 0,100% 0,94% 100%,0 100%)" }}>{m.competitionName}</Link>
            <h1 className="display-caps mt-3 text-5xl font-extrabold leading-[.95] sm:text-7xl" style={{ textShadow: "0 6px 40px rgba(0,0,0,.55)" }}>{m.competition === "UNL" ? m.edition : m.edition.replace(/[0-9]{4}/g, "").replace(/\s+/g, " ").trim()}<span className="block" style={{ color: theme.accent }}>{m.competition === "UNL" ? "" : m.year}</span></h1>
            <p className="mt-3 max-w-2xl text-base font-medium opacity-90 sm:text-lg">{m.competition === "UNL" ? "The Nations League keeps one logo across all editions." : theme.tagline}</p>
            <div className="mt-5 flex flex-wrap gap-2 text-xs font-bold uppercase tracking-wider">
              {soon && <span className="chip chip-soon !text-sm"><CalendarClock size={14} />{m.status === "upcoming" ? "Coming soon" : "Announced"}</span>}
              {m.host && <span className="bc-slant bg-white/15 px-4 py-1.5 backdrop-blur"><MapPin size={12} className="mr-1 inline" />{m.host}</span>}
              <span className="bc-slant bg-white/15 px-4 py-1.5 backdrop-blur">{fmtDate(m.start)} → {fmtDate(m.end)}</span>
              {m.teams && <span className="bc-slant bg-white/15 px-4 py-1.5 backdrop-blur"><Users size={12} className="mr-1 inline" />{m.teams} teams</span>}
            </div>
          </div>
          {!soon && m.champion && <motion.div initial={{ y: 30, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ delay: 0.4 }} className="relative overflow-hidden px-8 py-6 text-center text-slate-900 shadow-2xl" style={{ background: "linear-gradient(145deg,#fde68a,#f59e0b)", borderRadius: "var(--r)" }}>
            <Trophy className="mx-auto mb-1" size={34} /><div className="text-[11px] font-extrabold uppercase tracking-[0.3em]">Champion</div>
            <div className="mt-1 flex items-center justify-center gap-2 font-display text-3xl font-extrabold uppercase"><CountryFlag country={m.champion} size={34} />{m.champion}</div>
            {m.runnerUp && <div className="mt-1 flex items-center justify-center gap-1.5 text-xs font-semibold opacity-80">runner-up <CountryFlag country={m.runnerUp} size={18} />{m.runnerUp}</div>}</motion.div>}
        </div>
        {!soon && played > 0 && <div className="absolute inset-x-0 bottom-0 grid grid-cols-2 gap-px sm:grid-cols-4" style={{ background: "rgba(255,255,255,.14)" }}>
          {[["Matches", played], ["Goals", s.total_goals], ["Goals / match", Number(s.goals_per_match).toFixed(2)], ["Draw share", `${Number(s.draw_pct).toFixed(0)}%`]].map(([k, v]) => <div key={String(k)} className="px-4 py-3 text-center backdrop-blur" style={{ background: "rgba(4,8,18,.72)" }}><div className="font-display text-3xl font-bold tabular-nums" style={{ color: theme.accent }}>{v}</div><div className="text-[10px] font-bold uppercase tracking-[0.2em] opacity-75">{k}</div></div>)}</div>}
      </section>

      {soon && <Callout tone="soon" title={m.status === "upcoming" ? "Coming soon" : "Announced — details to be confirmed"} className="mb-6">
        {m.matchesComingSoon ? `${m.matchesComingSoon} fixtures are scheduled and kept in the data with whatever is known (date, stage, venue). ` : "No fixtures have been published yet. "}
        There are no results, statistics, awards or predictions for this edition: nothing is invented.</Callout>}

      <Tabs tabs={tabs} value={tab} onChange={setTab} id="tour" />
      <div className="pt-6">
        {tab === "Overview" && <>
          <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
            <KpiCard label="Matches played" value={played} icon={<Flag size={16} />} hint={m.matchesComingSoon ? `+ ${m.matchesComingSoon} coming soon` : undefined} />
            <KpiCard label="Goals" value={played ? s.total_goals : "–"} icon={<Goal size={16} />} />
            <KpiCard label="Goals per match" value={played ? Number(s.goals_per_match).toFixed(2) : "–"} icon={<Medal size={16} />} />
            <KpiCard label="Draw share" value={played ? `${Number(s.draw_pct).toFixed(1)}%` : "–"} icon={<Percent size={16} />} />
            <KpiCard label="Teams" value={m.teams ?? "–"} icon={<Users size={16} />} />
            <KpiCard label="Average attendance" value={s.avg_attendance ? Math.round(s.avg_attendance).toLocaleString() : "n/a"} hint="where recorded" />
            <KpiCard label="Matches beyond 90′" value={played ? s.matches_beyond_90 : "–"} />
            <KpiCard label="Shoot-outs" value={played ? s.shootouts : "–"} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="card p-5"><h3 className="mb-2 font-display font-bold">Format</h3><p className="text-sm">{m.format ?? "to be confirmed"}</p>
              <p className="mt-2 text-xs" style={{ color: "var(--c-muted)" }}>Data status: {m.verification ?? "n/a"}</p></div>
            <div className="card p-5"><h3 className="mb-2 font-display font-bold">Result</h3>
              {m.champion ? <p className="text-sm"><b>{m.champion}</b> won, <b>{m.runnerUp}</b> finished second.</p> : <p className="text-sm">{soon ? "Not played yet." : "Champion not recorded in the data."}</p>}
              {d.motmLeaders?.rows?.length > 0 && <p className="mt-2 text-sm">Most player-of-the-match awards: <b>{d.motmLeaders.rows[0].player}</b> ({d.motmLeaders.rows[0].awards}).</p>}</div>
          </div>
        </>}

        {tab === "Matches" && <Section title="All matches" hint="Click a match for its Match Center. Upcoming fixtures are shown as Coming soon.">
          <div className="mb-3 flex flex-wrap items-center gap-1.5">{stages.map((x) => <button key={x} onClick={() => setStage(x)} className={x === stage ? "chip" : "btn !rounded-full !py-0.5 !text-xs"}>{x}</button>)}
            <span className="ml-auto flex gap-1.5"><button className={view === "cards" ? "chip" : "btn !py-0.5 !text-xs"} onClick={() => setView("cards")}>Scoreboards</button><button className={view === "table" ? "chip" : "btn !py-0.5 !text-xs"} onClick={() => setView("table")}>Table</button></span></div>
          {view === "cards" ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{(d.matches?.rows ?? []).filter((r: any) => stage === "All" || r.stage_name === stage).map((r: any) => <FixtureCard key={r.match_key} m={{ ...r, had_shootout: r.home_pen != null, competition_id: m.competition, season_id: seasonId }} showComp={false} />)}</div>
            : <DataTable table={matchTable} pageSize={20} filename={`${seasonId}_matches`} hide={MATCH_HIDE} onRowClick={(r) => r.is_played && nav(`/match/${r.match_key}`)} empty="No matches in the data yet." />}
          {d.coverage && <p className="mt-3 text-xs" style={{ color: "var(--c-muted)" }}>Player of the match recorded for {d.coverage.withPlayerOfTheMatch} of {d.coverage.matchesPlayed} played matches. {d.coverage.playerOfTheMatchNote}</p>}
        </Section>}

        {tab === "Standings" && <Section title="Group standings" hint="Derived from the recorded 90-minute scores (3 points for a win).">{st.isLoading ? <Skeleton h={240} /> : <StandingsTable table={st.data?.table} />}</Section>}

        {tab === "Bracket" && <Section title="Knockout bracket" hint="Click a match for its Match Center."><Bracket matches={(d.matches?.rows ?? []).map((r: any) => ({ ...r, had_shootout: r.home_pen != null, competition_id: m.competition, season_id: seasonId }))} /></Section>}

        {tab === "Teams" && <Section title="Team table" hint="Played matches only. Result = recorded score (extra time included, shoot-outs excluded).">
          <DataTable table={d.teams} pageSize={40} filename={`${seasonId}_teams`} empty="No team results yet." /></Section>}

        {tab === "Awards" && <>
          <Section title="Individual awards" hint="Source: Wikipedia award pages."><DataTable table={d.awards} filename={`${seasonId}_awards`} empty={soon ? "No awards yet: this edition has not been played." : "No award rows were collected for this edition."} /></Section>
          <Section title="Team awards"><DataTable table={d.teamAwards} searchable={false} filename={`${seasonId}_team_awards`} empty="No team awards recorded." /></Section>
          <Section title="Top scorers (from goal events)" hint="Goals linked to a player; computed from recorded goal events, not an official table."><DataTable table={d.topScorers} filename={`${seasonId}_scorers`} empty="No linked scorers for this edition." /></Section>
          <Section title="Player-of-the-match leaders"><DataTable table={d.motmLeaders} searchable={false} filename={`${seasonId}_motm`} empty="Player of the match is not recorded for this edition." /></Section>
        </>}

        {tab === "Records" && <div className="grid gap-6 lg:grid-cols-2">
          <Section title="Highest-scoring matches"><DataTable table={d.highestScoring} searchable={false} filename={`${seasonId}_highest`} empty="No data." /></Section>
          <Section title="Biggest winning margins"><DataTable table={d.biggestMargins} searchable={false} filename={`${seasonId}_margins`} empty="No data." /></Section>
        </div>}

        {tab === "Charts" && (played ? <div>
          <ChartSection spec={{ id: "an.goal_minutes", title: "Goals by minute band", fixed: { comp: m.competition, season: seasonId } }} />
          <ChartSection spec={{ id: "comp.funnel", title: "Progression through the stages", fixed: { season: seasonId }, filtersOverride: filters }} />
          <ChartSection spec={{ id: "comp.groups", title: "Group standings", fixed: { season: seasonId } }} />
          <ChartSection spec={{ id: "comp.bracket", title: "Knockout bracket", fixed: { season: seasonId } }} />
          <ChartSection spec={{ id: "match.scoreline", title: "Scorelines", filtersOverride: filters }} />
        </div> : <ChartSection spec={{ id: "comp.bracket", title: "Bracket (fixtures)", fixed: { season: seasonId } }} />)}

        {tab === "Coverage" && <Section title="Data coverage" hint="What exists for this edition, so gaps are visible rather than hidden.">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <KpiCard label="Matches in dataset" value={s.matches_in_dataset ?? "–"} /><KpiCard label="Played" value={played} /><KpiCard label="Coming soon" value={m.matchesComingSoon} accent="#eab308" />
            <KpiCard label="Player of the match" value={d.coverage ? `${d.coverage.withPlayerOfTheMatch}/${d.coverage.matchesPlayed}` : "–"} icon={<Award size={16} />} /></div>
          <p className="mt-4 text-sm" style={{ color: "var(--c-muted)" }}>{d.coverage?.playerOfTheMatchNote}</p>
        </Section>}
      </div>
    </div>
  );
}
