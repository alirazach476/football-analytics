import { Table } from "../../api";
import TeamIdentity from "./TeamIdentity";

interface Metric { key: string; label: string; pct?: boolean; dec?: number }
// Only metrics a source records are drawn (warehouse StatsBomb stats have no possession/offsides/saves; the Finalissima match report does). A missing metric is skipped, never zero.
export const METRICS: Metric[] = [
  { key: "possession", label: "Possession", pct: true }, { key: "xg", label: "Expected goals (xG)", dec: 2 }, { key: "shots", label: "Total shots" }, { key: "shots_on_target", label: "Shots on target" }, { key: "passes", label: "Passes" },
  { key: "pass_accuracy", label: "Pass accuracy", pct: true }, { key: "corners_taken", label: "Corners" }, { key: "fouls_committed", label: "Fouls committed" }, { key: "yellow_cards", label: "Yellow cards" }, { key: "red_cards", label: "Red cards" }, { key: "offsides", label: "Offsides" }, { key: "saves", label: "Saves" },
];
const fmt = (v: number, m: Metric) => (m.pct ? `${Math.round(v * 100)}%` : m.dec ? v.toFixed(m.dec) : Math.round(v).toLocaleString("en-US"));

export function statRows(stats: Table | undefined, home: string, away: string) {
  const h = stats?.rows.find((r) => r.team_name === home), a = stats?.rows.find((r) => r.team_name === away);
  if (!h || !a) return [];
  return METRICS.filter((m) => h[m.key] != null && a[m.key] != null).map((m) => ({ m, h: Number(h[m.key]), a: Number(a[m.key]) }));   // a missing value is skipped, never shown as 0
}

export default function StatisticsComparison({ stats, home, away }: { stats?: Table; home: string; away: string }) {
  const rows = statRows(stats, home, away);
  if (!rows.length) return null;
  return (
    <div className="card p-5 sm:p-6" role="table" aria-label="Team statistics comparison">
      <div className="mb-5 grid grid-cols-2 gap-4"><TeamIdentity name={home} size="md" /><div className="flex justify-end"><TeamIdentity name={away} size="md" align="right" /></div></div>
      <div className="space-y-5">
        {rows.map(({ m, h, a }) => {
          const tot = h + a; const hs = m.pct ? h : tot ? h / tot : 0.5, as = m.pct ? a : tot ? a / tot : 0.5; const hl = h > a, al = a > h;
          return (
            <div key={m.key} role="row">
              <div className="mb-1.5 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-baseline gap-3">
                <span className={`font-display text-2xl tabular-nums ${hl ? "font-black" : "font-semibold opacity-70"}`} style={{ color: hl ? "var(--c-primary)" : undefined }}>{fmt(h, m)}</span>
                <span className="text-center text-xs font-bold uppercase tracking-[0.14em]" style={{ color: "var(--c-muted)" }}>{m.label}</span>
                <span className={`text-right font-display text-2xl tabular-nums ${al ? "font-black" : "font-semibold opacity-70"}`} style={{ color: al ? "var(--c-secondary)" : undefined }}>{fmt(a, m)}</span>
              </div>
              <div className="flex gap-1.5" aria-hidden>
                <div className="flex h-2.5 flex-1 justify-end overflow-hidden rounded-full" style={{ background: "color-mix(in srgb, var(--c-muted) 18%, transparent)" }}><div className="bar-grow bar-grow-l h-full rounded-full" style={{ width: `${Math.min(100, hs * 100)}%`, background: "var(--c-primary)", opacity: hl || h === a ? 1 : 0.55 }} /></div>
                <div className="flex h-2.5 flex-1 overflow-hidden rounded-full" style={{ background: "color-mix(in srgb, var(--c-muted) 18%, transparent)" }}><div className="bar-grow bar-grow-r h-full rounded-full" style={{ width: `${Math.min(100, as * 100)}%`, background: "var(--c-secondary)", opacity: al || h === a ? 1 : 0.55 }} /></div>
              </div>
            </div>);
        })}
      </div>
    </div>
  );
}
