import { Table } from "../../api";
import CountryFlag from "../CountryFlag";
import { Link } from "react-router-dom";
import { dateLabel } from "./matchUtils";

/** Historical meetings between two teams in the four competitions (recorded score, extra time included, shoot-outs excluded). */
export default function HeadToHead({ table, a, b, currentDate }: { table?: Table; a: string; b: string; currentDate?: string }) {
  const rows = table?.rows ?? [];
  if (!rows.length) return <div className="card p-4 text-sm" style={{ color: "var(--c-muted)" }}>These teams have not met in the collected competitions.</div>;
  let wa = 0, wb = 0, d = 0, ga = 0, gb = 0;
  rows.forEach((r) => { const sa = r.home_team_name === a ? r.home_score : r.away_score, sb = r.home_team_name === a ? r.away_score : r.home_score; ga += sa; gb += sb; if (sa > sb) wa++; else if (sb > sa) wb++; else d++; });
  const n = rows.length; const bar = (v: number, c: string) => <div style={{ width: `${(v / n) * 100}%`, background: c }} className="h-full" title={String(v)} />;
  return (
    <div className="space-y-5">
      <div className="card p-5">
        <div className="mb-3 grid grid-cols-[1fr_auto_1fr] items-center gap-3 text-center">
          <div><CountryFlag country={a} size={40} className="mx-auto" /><div className="mt-1 font-display font-bold">{a}</div><div className="font-display text-4xl font-black tabular-nums" style={{ color: "var(--c-primary)" }}>{wa}</div><div className="text-xs" style={{ color: "var(--c-muted)" }}>wins</div></div>
          <div><div className="font-display text-4xl font-black tabular-nums">{d}</div><div className="text-xs" style={{ color: "var(--c-muted)" }}>draws</div><div className="mt-2 text-xs" style={{ color: "var(--c-muted)" }}>{n} meeting{n === 1 ? "" : "s"}</div></div>
          <div><CountryFlag country={b} size={40} className="mx-auto" /><div className="mt-1 font-display font-bold">{b}</div><div className="font-display text-4xl font-black tabular-nums" style={{ color: "var(--c-secondary)" }}>{wb}</div><div className="text-xs" style={{ color: "var(--c-muted)" }}>wins</div></div>
        </div>
        <div className="flex h-3 overflow-hidden rounded-full" aria-hidden>{bar(wa, "var(--c-primary)")}{bar(d, "color-mix(in srgb, var(--c-muted) 55%, transparent)")}{bar(wb, "var(--c-secondary)")}</div>
        <p className="mt-3 text-center text-sm">Goals: <b>{a} {ga}</b> – <b>{gb} {b}</b> · {((ga + gb) / n).toFixed(2)} per meeting</p>
      </div>
      <div className="card overflow-hidden"><h3 className="border-b px-4 py-2 text-xs font-extrabold uppercase tracking-[0.18em]" style={{ borderColor: "var(--c-border)" }}>All meetings (most recent first)</h3>
        <ul>{rows.map((r, i) => { const cur = currentDate && String(r.match_date).slice(0, 10) === String(currentDate).slice(0, 10);
          return <li key={i} className="grid grid-cols-[5.5rem_1fr_auto_1fr] items-center gap-2 border-t px-4 py-2 text-sm" style={{ borderColor: "var(--c-border)", background: cur ? "color-mix(in srgb, var(--c-primary) 12%, transparent)" : undefined }}>
            <span className="text-xs tabular-nums" style={{ color: "var(--c-muted)" }}>{dateLabel(r.match_date)}</span>
            <span className="flex items-center justify-end gap-2 text-right font-semibold"><span className="truncate">{r.home_team_name}</span><CountryFlag country={r.home_team_name} size={20} /></span>
            {r.match_key != null ? <Link to={`/match/${r.match_key}`} title="Open match" className="rounded-md px-2 font-display font-black tabular-nums hover:underline" style={{ background: "color-mix(in srgb, var(--c-muted) 20%, transparent)" }}>{r.home_score}–{r.away_score}</Link> : <span className="rounded-md px-2 font-display font-black tabular-nums" style={{ background: "color-mix(in srgb, var(--c-muted) 20%, transparent)" }}>{r.home_score}–{r.away_score}</span>}
            <span className="flex items-center gap-2 font-semibold"><CountryFlag country={r.away_team_name} size={20} /><span className="truncate">{r.away_team_name}</span><span className="ml-auto hidden text-xs font-normal sm:inline" style={{ color: "var(--c-muted)" }}>{r.season_id} · {r.stage_name}</span></span></li>; })}</ul></div>
    </div>
  );
}
