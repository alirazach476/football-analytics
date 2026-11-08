import { Table } from "../../api";
import CountryFlag from "../CountryFlag";

/** Group tables: POS | flag | team | MP W D L GF GA GD PTS. Top two of each group get a qualification marker (the usual first-round rule; the data holds no per-edition qualification rule, so this is indicative). */
export default function StandingsTable({ table, qualifiers = 2 }: { table?: Table; qualifiers?: number }) {
  const rows = table?.rows ?? [];
  if (!rows.length) return <div className="card p-4 text-sm" style={{ color: "var(--c-muted)" }}>No group standings for this edition (no group stage, or it has not been played yet).</div>;
  const groups = Array.from(new Set(rows.map((r) => r.group_name ?? "–")));
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      {groups.map((g) => (
        <div key={g} className="card overflow-hidden">
          <div className="border-b px-4 py-2 text-xs font-extrabold uppercase tracking-[0.18em]" style={{ borderColor: "var(--c-border)", color: "var(--c-primary)" }}>Group {g}</div>
          <table className="w-full text-sm"><thead><tr style={{ color: "var(--c-muted)" }} className="text-[11px] uppercase tracking-wide">
            <th className="px-3 py-2 text-left">#</th><th className="py-2 text-left" colSpan={2}>Team</th>{["MP", "W", "D", "L", "GF", "GA", "GD", "PTS"].map((h) => <th key={h} className="px-2 py-2 text-right">{h}</th>)}</tr></thead>
            <tbody>{rows.filter((r) => (r.group_name ?? "–") === g).map((r) => { const q = r.group_position <= qualifiers;
              return <tr key={r.team_name} className="border-t" style={{ borderColor: "var(--c-border)", boxShadow: q ? "inset 3px 0 0 var(--c-primary)" : undefined }}>
                <td className="px-3 py-2 font-bold tabular-nums">{r.group_position}</td><td className="w-8 py-2"><CountryFlag country={r.team_name} size={22} /></td><td className="py-2 pr-2 font-semibold">{r.team_name}</td>
                {[r.played, r.wins, r.draws, r.losses, r.goals_for, r.goals_against, r.goal_difference > 0 ? `+${r.goal_difference}` : r.goal_difference].map((v, i) => <td key={i} className="px-2 py-2 text-right tabular-nums">{v}</td>)}
                <td className="px-2 py-2 text-right text-base font-black tabular-nums">{r.points}</td></tr>; })}</tbody></table>
        </div>))}
      <p className="col-span-full text-xs" style={{ color: "var(--c-muted)" }}>Basis: {String(rows[0].basis ?? "derived from matches")}. The coloured bar marks the top {qualifiers} of each group.</p>
    </div>
  );
}
