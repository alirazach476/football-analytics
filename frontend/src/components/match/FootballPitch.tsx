import { ReactNode } from "react";
import { Table } from "../../api";
import CountryFlag from "../CountryFlag";
import { teamPalette } from "../../data/teamColors";

export interface Player { team_name: string; player: string; jersey_number?: number | null; is_starter?: boolean | null; minutes_played?: number | null; note?: string | null; primary_position?: string | null; line?: string | null }

// recorded position -> short code, formation line and lateral weight (left 0 .. right 1). Unknown positions are never guessed.
const POS: Record<string, [string, "GK" | "DF" | "DM" | "MF" | "AM" | "FW", number]> = {
  Goalkeeper: ["GK", "GK", 0.5],
  Defender: ["DF", "DF", 0.5], "Center Back": ["CB", "DF", 0.5], "Left Center Back": ["CB", "DF", 0.35], "Right Center Back": ["CB", "DF", 0.65], "Left Back": ["LB", "DF", 0.05], "Right Back": ["RB", "DF", 0.95],
  "Left Wing Back": ["LWB", "DF", 0.05], "Right Wing Back": ["RWB", "DF", 0.95],
  "Defensive Midfield": ["DM", "DM", 0.5], "Left Defensive Midfield": ["DM", "DM", 0.35], "Right Defensive Midfield": ["DM", "DM", 0.65],
  Midfielder: ["MF", "MF", 0.5], "Center Midfield": ["CM", "MF", 0.5], "Left Center Midfield": ["CM", "MF", 0.35], "Right Center Midfield": ["CM", "MF", 0.65], "Left Midfield": ["LM", "MF", 0.05], "Right Midfield": ["RM", "MF", 0.95],
  "Attacking Midfield": ["AM", "AM", 0.5], "Center Attacking Midfield": ["AM", "AM", 0.5], "Center Defensive Midfield": ["DM", "DM", 0.5], "Left Attacking Midfield": ["AM", "AM", 0.3], "Right Attacking Midfield": ["AM", "AM", 0.7],
  Forward: ["FW", "FW", 0.5], "Center Forward": ["ST", "FW", 0.5], "Left Center Forward": ["ST", "FW", 0.4], "Right Center Forward": ["ST", "FW", 0.6], Striker: ["ST", "FW", 0.5], "Secondary Striker": ["SS", "FW", 0.5],
  "Left Wing": ["LW", "FW", 0.08], "Right Wing": ["RW", "FW", 0.92],
};
const LINES: ("FW" | "AM" | "MF" | "DM" | "DF" | "GK")[] = ["FW", "AM", "MF", "DM", "DF", "GK"];     // attack at the top of the pitch
const info = (p: Player) => POS[p.primary_position ?? ""];
const tagName = (n: string) => { const w = n.trim().split(/\s+/); return (w.length <= 2 ? w[w.length - 1] : n).toUpperCase(); };   // long legal names are shown in full: a surname guess would be wrong for many

/** Dark pitch with bright markings (own half at the bottom, goal box under the keeper), like a TV line-up graphic. */
export function FootballPitch({ children, lines = 5 }: { children?: ReactNode; lines?: number }) {
  const H = Math.round(100 * (lines + 1.4));   // tall enough for one card per line, goalkeeper included
  return (
    <div className="relative mx-auto w-full overflow-hidden rounded-2xl" style={{ aspectRatio: `400 / ${H}`, background: "linear-gradient(180deg, #05402f, #04523a 50%, #05402f)" }}>
      <svg viewBox={`0 0 400 ${H}`} className="absolute inset-0 h-full w-full" fill="none" stroke="#1fd36b" strokeWidth="2.2" aria-hidden>
        <rect x="14" y="26" width="372" height={H - 40} /><path d="M140 26 a60 60 0 0 0 120 0" />
        <rect x="110" y={H - 120} width="180" height="106" /><rect x="152" y={H - 62} width="96" height="48" /><path d={`M162 ${H - 120} a38 38 0 0 1 76 0`} /><circle cx="200" cy={H - 98} r="2.5" fill="#1fd36b" />
        <path d={`M14 ${H - 28} a14 14 0 0 0 14 14`} /><path d={`M386 ${H - 28} a14 14 0 0 1 -14 14`} />
      </svg>
      {children}
    </div>
  );
}

function Avatar({ kit, gk }: { kit: string; gk: boolean }) {
  const shirt = gk ? "#16a34a" : kit;
  return (
    <svg viewBox="0 0 60 64" className="h-full w-full" aria-hidden>
      <rect width="60" height="64" fill="#f8fafc" />
      <path d="M6 64 C6 46 18 40 30 40 C42 40 54 46 54 64 Z" fill={shirt} />
      <path d="M23 40 L30 49 L37 40 Z" fill="rgba(255,255,255,.55)" />
      <circle cx="30" cy="25" r="12" fill="#cbd5e1" /><path d="M18 22 a12 12 0 0 1 24 0 c-4 -5 -20 -5 -24 0z" fill="#94a3b8" />
    </svg>
  );
}

function PlayerCard({ p, kit }: { p: Player; kit: string }) {
  const code = info(p)?.[0] ?? p.primary_position?.slice(0, 2).toUpperCase() ?? "";
  return (
    <div className="group flex w-[19%] min-w-[58px] max-w-[96px] flex-col items-stretch drop-shadow-xl transition hover:-translate-y-1" title={`${p.player}${p.primary_position ? ` · ${p.primary_position}` : ""}`}>
      <div className="overflow-hidden rounded-[4px] border-2 border-white bg-white">
        <div className="flex items-center justify-between bg-black px-1 py-px leading-none"><span className="text-[9px] font-bold text-white sm:text-[10px]">{code}</span><span className="font-display text-xs font-bold sm:text-sm" style={{ color: "#22e07a" }}>{p.jersey_number ?? "–"}</span></div>
        <div className="aspect-[15/16] w-full"><Avatar kit={kit} gk={info(p)?.[1] === "GK"} /></div>
      </div>
      <div className="-mt-px line-clamp-3 min-h-[2.7em] rounded-b-[4px] px-0.5 py-0.5 text-center text-[8px] font-extrabold leading-tight tracking-wide text-black sm:text-[10px]" style={{ background: "#e8ff2e" }}>{tagName(p.player)}</div>
    </div>
  );
}

/** Team banner under the pitch: flag + name on black with curved bands in the national colours. */
function TeamBanner({ team, c1, c2, shape, manager }: { team: string; c1: string; c2: string; shape?: string; manager?: Manager }) {
  return (
    <div className="relative mt-4 overflow-hidden rounded-b-[44px] rounded-t-[26px]" style={{ background: c1 }}>
      <div className="m-[7px] rounded-b-[38px] rounded-t-[20px] p-[7px]" style={{ background: c2 }}>
        <div className="flex items-center gap-4 rounded-b-[32px] rounded-t-[14px] bg-black px-5 py-4 sm:gap-6 sm:px-8 sm:py-5">
          <CountryFlag country={team} size={72} className="!rounded-sm" />
          <div className="min-w-0"><div className="truncate font-display text-3xl font-bold uppercase leading-none text-white sm:text-5xl">{team}</div>{shape && <div className="mt-1 text-xs font-bold uppercase tracking-[0.3em]" style={{ color: "#e8ff2e" }}>Formation {shape}</div>}{manager && <div className="mt-1 text-sm font-semibold text-white/90" title={manager.level === "tournament" ? "Head coach of the team at this tournament (not confirmed per match)" : "Manager recorded for this match"}>Manager: {manager.name}{manager.level === "tournament" ? " · tournament head coach" : ""}</div>}</div>
        </div>
      </div>
    </div>
  );
}

/** Broadcast line-up: starting XI laid out on the pitch by recorded position (lines and left/right order), substitutes below. The shape (e.g. 4-2-3-1) is derived from those positions, not from tracking data. */
export interface Manager { name: string; source: string; level: string }
export default function TeamLineup({ team, players, color, manager }: { team: string; players: Player[]; color?: string; manager?: Manager }) {
  const [c1, c2] = teamPalette(team, [color ?? "#334155", "#94a3b8"]);
  const starters = players.filter((p) => p.is_starter), bench = players.filter((p) => !p.is_starter);
  const usePitch = starters.length >= 9 && starters.every((p) => info(p));
  const lines = LINES.map((l) => ({ l, ps: starters.filter((p) => info(p)?.[1] === l).sort((a, b) => info(a)![2] - info(b)![2]) })).filter((x) => x.ps.length);
  const generic = starters.some((p) => ["Defender", "Midfielder", "Forward"].includes(p.primary_position ?? ""));
  const shape = lines.filter((x) => x.l !== "GK").map((x) => x.ps.length).reverse().join("-");
  return (
    <div>
      {usePitch ? (
        <FootballPitch lines={lines.length}>
          <div className="absolute inset-0 flex flex-col justify-between px-2 pb-3 pt-4 sm:px-4">
            {lines.map(({ l, ps }) => <div key={l} className="flex items-start justify-around gap-1">{ps.map((p) => <PlayerCard key={p.player} p={p} kit={c1} />)}</div>)}
          </div>
        </FootballPitch>
      ) : (
        <div className="card p-4">
          <p className="mb-2 text-xs" style={{ color: "var(--c-muted)" }}>{starters.length ? "Positions are not recorded for every starter, so the players are listed instead of placed on a pitch." : "No starting line-up recorded."}</p>
          <ul className="grid gap-1 sm:grid-cols-2">{starters.map((p) => <li key={p.player} className="flex items-center gap-2 text-sm"><span className="grid h-6 w-6 place-items-center rounded-full text-[11px] font-bold text-white" style={{ background: c1 }}>{p.jersey_number ?? "–"}</span>{p.player}</li>)}</ul>
        </div>
      )}
      {usePitch && generic && <p className="mt-2 text-center text-[11px]" style={{ color: "var(--c-muted)" }}>Some players only have a general position (defender, midfielder or forward), so their left-to-right order within a line is not known.</p>}
      <TeamBanner team={team} c1={c1} c2={c2} shape={usePitch ? shape : undefined} manager={manager} />
      {bench.length > 0 && <div className="card mt-4 p-4"><h4 className="mb-2 text-xs font-bold uppercase tracking-[0.2em]" style={{ color: "var(--c-muted)" }}>Substitutes</h4>
        <ul className="grid gap-1.5 sm:grid-cols-2">{bench.map((p) => <li key={p.player} className="flex items-center justify-between gap-2 text-sm"><span className="flex min-w-0 items-center gap-2"><span className="grid h-6 w-7 shrink-0 place-items-center rounded-sm text-[11px] font-bold" style={{ background: "#e8ff2e", color: "#000" }}>{p.jersey_number ?? "–"}</span><span className="truncate">{p.player}</span></span>
          {p.note ? <span className="chip whitespace-nowrap !py-0 !text-[10px]" style={{ color: "var(--c-ink)" }}>{p.note}</span> : p.minutes_played ? <span className="chip whitespace-nowrap !py-0 !text-[10px]" style={{ color: "var(--c-ink)" }} title="minutes played">{Math.round(p.minutes_played)}′</span> : <span className="text-[10px]" style={{ color: "var(--c-muted)" }}>unused</span>}</li>)}</ul></div>}
    </div>
  );
}
export const playersOf = (t: Table | undefined, team: string) => (t?.rows ?? []).filter((r) => r.team_name === team) as Player[];
