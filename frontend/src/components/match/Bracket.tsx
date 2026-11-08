import { Link } from "react-router-dom";
import CountryFlag from "../CountryFlag";
import { MatchRow, statusOf } from "./matchUtils";

const KO = ["Round of 32", "Round of 16", "Quarter-finals", "Semi-finals", "Third place", "Final"];

/** Knockout bracket as columns by stage. Fixtures with undecided teams show their placeholder (e.g. Winner Group A) and Coming soon. */
export default function Bracket({ matches }: { matches: MatchRow[] }) {
  const stages = KO.filter((s) => matches.some((m) => m.stage_name === s));
  if (!stages.length) return <div className="card p-4 text-sm" style={{ color: "var(--c-muted)" }}>This edition has no knockout stage in the data.</div>;
  return (
    <div className="overflow-x-auto pb-3"><div className="flex min-w-max gap-5">
      {stages.map((s) => (
        <div key={s} className="flex w-60 flex-col justify-around gap-3">
          <h3 className="text-center text-xs font-extrabold uppercase tracking-[0.18em]" style={{ color: "var(--c-primary)" }}>{s}</h3>
          {matches.filter((m) => m.stage_name === s).map((m) => { const played = m.is_played && m.home_score != null; const { status } = statusOf(m);
            const win = (side: "home" | "away") => !!played && ((side === "home" ? m.home_score! > m.away_score! : m.away_score! > m.home_score!) || !!(m.had_shootout && m.shootout_winner_side === side));
            const line = (name: string, sc: number | null | undefined, pen: number | null | undefined, w: boolean) => (
              <div className={`flex items-center justify-between gap-2 px-3 py-1.5 ${w ? "font-bold" : "opacity-80"}`}><span className="flex min-w-0 items-center gap-2"><CountryFlag country={name} size={20} /><span className="truncate text-sm">{name}</span></span>
                <span className="tabular-nums">{played ? sc : ""}{played && m.had_shootout && pen != null ? <sup className="ml-0.5 text-[10px]">({pen})</sup> : null}</span></div>);
            return <Link key={m.match_key} to={`/match/${m.match_key}`} className="card block overflow-hidden transition hover:shadow-glow" aria-label={`${m.home_team_name} v ${m.away_team_name}`}>
              {line(m.home_team_name, m.home_score, m.home_pen, win("home"))}<div style={{ borderTop: "1px solid var(--c-border)" }} />{line(m.away_team_name, m.away_score, m.away_pen, win("away"))}
              {status === "Scheduled" && <div className="chip-soon px-3 py-0.5 text-center text-[10px] font-bold uppercase">Coming soon</div>}</Link>; })}
        </div>))}
    </div></div>
  );
}
