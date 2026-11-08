import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Clock } from "lucide-react";
import { useApiQuery, useTournaments } from "../api";
import { THEMES } from "../theme/editions";
import { Callout, KpiCard, Section, Skeleton } from "../components/ui";
import { BrandLogos } from "../components/Brand";

const COMPS = [
  ["WC", "FIFA World Cup", "wc-2026", "2002 – 2026, plus World Cup 2030 coming soon"],
  ["EURO", "UEFA European Championship", "euro-2024", "Euro 2000 – 2024, plus Euro 2028 coming soon"],
  ["COPA", "Copa América", "copa-2024", "Copa 2001 – 2024, plus Copa 2028 announced"],
  ["UNL", "UEFA Nations League", "unl", "One identity, every edition"],
] as const;

export default function Home() {
  const { data: tl } = useTournaments(); const k = useApiQuery<any>("kpis"); const dq = useApiQuery<any>("data_quality_score");
  const kk = k.data;
  return (
    <div>
      <section className="relative mb-8 overflow-hidden rounded-3xl border p-8 sm:p-12" style={{ borderColor: "var(--c-border)", background: "linear-gradient(120deg,var(--c-hero-from),var(--c-hero-to))" }}>
        <div className="pattern-grid absolute inset-0 opacity-60" />
        <div className="relative max-w-3xl text-white">
          <BrandLogos size={64} className="mb-5" />
          <div className="mb-3 text-xs font-bold uppercase tracking-[0.2em] opacity-80">World Cup · Euro · Copa América · Nations League</div>
          <h1 className="font-display text-3xl font-extrabold leading-tight sm:text-5xl">Men's national-team football, analysed edition by edition.</h1>
          <p className="mt-4 max-w-2xl text-base opacity-90">Every tournament has its own page, styled after its logo. Results are never invented, missing data stays empty, and fixtures that have not been played say <b>Coming soon</b>.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/analytics/overview" className="btn btn-primary">Open analytics <ArrowRight size={15} /></Link>
          </div>
        </div>
      </section>
      <Section title="At a glance">
        {kk ? <div className="grid grid-cols-2 gap-4 md:grid-cols-4 xl:grid-cols-5">
          <KpiCard label="Competitions" value={kk.competitions} />
          <KpiCard label="Editions with matches" value={kk.editions_played} hint={`plus ${kk.editions_upcoming} upcoming edition(s)`} />
          <KpiCard label="Matches played" value={kk.matches_played.toLocaleString()} />
          <KpiCard label="Teams" value={kk.teams} />
          <KpiCard label="Players" value={kk.players.toLocaleString()} hint="after merging duplicate identities" />
          <KpiCard label="Goals (recorded)" value={kk.goals.toLocaleString()} />
          <KpiCard label="Match events" value={kk.events.toLocaleString()} />
          <KpiCard label="Venues" value={kk.venues} />
          <KpiCard label="Coming soon" value={kk.matches_coming_soon} hint="scheduled fixtures kept in the data" accent="#eab308" />
          <KpiCard label="Data quality score" value={dq.data?.score == null ? "n/a" : `${Math.round(dq.data.score)}%`} hint="rule compliance, not completeness" />
        </div> : <Skeleton h={180} />}
      </Section>
      <Section title="Tournaments" hint="Pick a competition, then an edition: each page uses that edition's own logo, colours and artwork.">
        <div className="grid gap-5 md:grid-cols-2">
          {COMPS.map(([id, label, flag, blurb], i) => { const t = THEMES[flag]; const n = tl?.editions.filter((e) => e.competition === id).length;
            return (
              <motion.div key={id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
                <Link to={`/competition/${id.toLowerCase()}`} className="group relative block overflow-hidden rounded-2xl border p-6 transition hover:-translate-y-0.5 hover:shadow-glow" style={{ borderColor: "var(--c-border)", background: `linear-gradient(135deg, ${t.heroFrom}, ${t.heroTo})` }}>
                  <div className={`pattern-${t.pattern} absolute inset-0`} />
                  <div className="relative flex items-center gap-5 text-white">
                    <img src={t.logo} alt={`${label} logo`} className="h-24 w-24 rounded-2xl bg-white/90 object-contain p-2 transition group-hover:scale-105" />
                    <div><h3 className="font-display text-xl font-bold">{label}</h3><p className="text-sm opacity-85">{blurb}</p><p className="mt-2 text-xs font-semibold opacity-90">{n ?? "…"} editions <ArrowRight size={12} className="inline" /></p></div>
                  </div>
                </Link>
              </motion.div>); })}
        </div>
      </Section>
      <Callout tone="info" title="How to read this dashboard">The <b>Analytics</b> pages are the original dashboard views; the <b>Visualization lab</b> adds the full chart library with shared filters, cross-filtering, a table view and downloads for every chart. The Champions League is deliberately not part of this project.</Callout>
    </div>
  );
}
