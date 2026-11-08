import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Download, Search } from "lucide-react";
import { Table, saveBlob } from "../api";
import { StatusBadge, cx } from "./ui";
import CountryFlag from "./CountryFlag";
import { flagCode } from "../data/countries";

const TEAM_COL = /^(team|team_name|home_team_name|away_team_name|team_a|team_b|champion|runner_up|runnerup|opponent|nationality|a|b)$/i;

const fmt = (v: any, col: string): string => {
  if (v === null || v === undefined || v === "") return "–";
  if (typeof v === "number") {
    if (/year|key|id$|^n$|season/i.test(col) && Number.isInteger(v)) return String(v);
    return Number.isInteger(v) ? v.toLocaleString("en-US") : Math.abs(v) >= 100 ? v.toLocaleString("en-US", { maximumFractionDigits: 1 }) : String(Math.round(v * 1000) / 1000);
  }
  if (typeof v === "boolean") return v ? "yes" : "no";
  const s = String(v);
  return /^\d{4}-\d{2}-\d{2} 00:00:00$/.test(s) ? s.slice(0, 10) : s;
};
export const toCsv = (t: Table) => {
  const esc = (v: any) => { const s = v === null || v === undefined ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  return "﻿" + [t.columns.join(","), ...t.rows.map((r) => t.columns.map((c) => esc(r[c])).join(","))].join("\n");
};

export default function DataTable({ table, pageSize = 15, searchable = true, filename = "table", hide = [], dense = false, onRowClick, empty = "No rows." }:
  { table?: Table; pageSize?: number; searchable?: boolean; filename?: string; hide?: string[]; dense?: boolean; onRowClick?: (row: Record<string, any>) => void; empty?: string }) {
  const [q, setQ] = useState(""); const [sort, setSort] = useState<{ col: string; dir: 1 | -1 } | null>(null); const [page, setPage] = useState(0);
  const cols = useMemo(() => (table?.columns ?? []).filter((c) => !hide.includes(c)), [table, hide]);
  const rows = useMemo(() => {
    let r = table?.rows ?? [];
    if (q) { const s = q.toLowerCase(); r = r.filter((x) => cols.some((c) => String(x[c] ?? "").toLowerCase().includes(s))); }
    if (sort) r = [...r].sort((a, b) => { const x = a[sort.col], y = b[sort.col]; if (x == null) return 1; if (y == null) return -1; return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))) * sort.dir; });
    return r;
  }, [table, q, sort, cols]);
  const pages = Math.max(1, Math.ceil(rows.length / pageSize)); const cur = Math.min(page, pages - 1);
  if (!table || !table.rows.length) return <div className="rounded-xl border p-4 text-sm" style={{ borderColor: "var(--c-border)", color: "var(--c-muted)" }}>{empty}</div>;
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        {searchable ? <div className="relative"><Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--c-muted)" }} />
          <input className="field w-56 pl-8" placeholder="Filter rows…" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} aria-label="Filter rows" /></div> : <span />}
        <div className="flex items-center gap-2 text-xs" style={{ color: "var(--c-muted)" }}>
          {rows.length.toLocaleString()} row{rows.length === 1 ? "" : "s"}{table.total > table.rows.length && ` (first ${table.rows.length.toLocaleString()} of ${table.total.toLocaleString()})`}
          <button className="btn !py-1" onClick={() => saveBlob(new Blob([toCsv({ ...table, rows })], { type: "text/csv" }), `${filename}.csv`)}><Download size={14} />CSV</button>
        </div>
      </div>
      <div className="overflow-auto rounded-xl border" style={{ borderColor: "var(--c-border)", maxHeight: 560 }}>
        <table className="w-full border-collapse">
          <thead className="sticky top-0 z-10" style={{ background: "var(--c-surface-solid)" }}>
            <tr>{cols.map((c) => (
              <th key={c} className="th cursor-pointer" onClick={() => setSort((s) => (s?.col === c ? (s.dir === 1 ? { col: c, dir: -1 } : null) : { col: c, dir: 1 }))} aria-sort={sort?.col === c ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
                <span className="inline-flex items-center gap-1">{c.replace(/_/g, " ")}{sort?.col === c && (sort.dir === 1 ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}</span></th>))}</tr>
          </thead>
          <tbody>
            {rows.slice(cur * pageSize, cur * pageSize + pageSize).map((r, i) => (
              <tr key={i} onClick={onRowClick ? () => onRowClick(r) : undefined} className={cx("border-t transition hover:bg-white/5", onRowClick && "cursor-pointer")} style={{ borderColor: "var(--c-border)" }}>
                {cols.map((c) => { const v = r[c]; const num = typeof v === "number";
                  return <td key={c} className={cx("td", dense && "!py-1", num && "text-right tabular-nums")}>{c === "status_label" && typeof v === "string" ? <StatusBadge text={v} /> : TEAM_COL.test(c) && typeof v === "string" && flagCode(v) ? <span className="inline-flex items-center gap-2"><CountryFlag country={v} size={20} />{v}</span> : fmt(v, c)}</td>; })}
              </tr>))}
          </tbody>
        </table>
      </div>
      {pages > 1 && <div className="mt-2 flex items-center justify-end gap-2 text-sm">
        <button className="btn !py-1" disabled={cur === 0} onClick={() => setPage(cur - 1)}>Prev</button>
        <span style={{ color: "var(--c-muted)" }}>Page {cur + 1} / {pages}</span>
        <button className="btn !py-1" disabled={cur >= pages - 1} onClick={() => setPage(cur + 1)}>Next</button></div>}
    </div>
  );
}
