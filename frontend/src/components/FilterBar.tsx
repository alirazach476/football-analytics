import { useState } from "react";
import { ChevronDown, Download, RotateCcw, SlidersHorizontal } from "lucide-react";
import { saveBlob, useLookups } from "../api";
import { describeFilters, useFilters } from "../state/filters";
import { MultiSelect, Row } from "./controls";
import { HUB_THEME } from "../theme/editions";
import { useThemeOverride } from "../theme/useTheme";

export default function FilterBar({ teams = true, stages = true, download }: { teams?: boolean; stages?: boolean; download?: "matches" | "players" }) {
  const { filters, set, reset, active } = useFilters();
  // a single edition (or competition) in the filters re-themes the lab page with that tournament logo design
  useThemeOverride(filters.seasons.length === 1 ? filters.seasons[0] : filters.competitions.length === 1 ? HUB_THEME[filters.competitions[0]] : null); const { data: lk } = useLookups(); const [open, setOpen] = useState(true);
  if (!lk) return <div className="skeleton mb-5 h-14" />;
  const seasons = lk.seasons.filter((s) => !filters.competitions.length || filters.competitions.includes(s.competition)).map((s) => s.seasonId);
  const dl = async () => {
    const r = await fetch("/api/filtered", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: download, filters }) });
    if (r.ok) saveBlob(await r.blob(), `filtered_${download}.csv`);
  };
  return (
    <div className="card mb-6 p-4 no-print">
      <button className="flex w-full items-center justify-between text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span className="flex items-center gap-2 text-sm font-bold"><SlidersHorizontal size={16} style={{ color: "var(--c-primary)" }} />Filters<span className="font-normal" style={{ color: "var(--c-muted)" }}>· {describeFilters(filters)}</span></span>
        <ChevronDown size={16} className={open ? "rotate-180 transition" : "transition"} />
      </button>
      {open && (
        <Row className="mt-4">
          <MultiSelect label="Competition" value={filters.competitions} onChange={(v) => set({ competitions: v, seasons: filters.seasons.filter((s) => v.length === 0 || v.includes(s.split("-")[0])) })} options={lk.competitions.map((c) => [c.id, c.label] as [string, string])} searchable={false} />
          <MultiSelect label="Edition / season" value={filters.seasons} onChange={(v) => set({ seasons: v })} options={seasons} />
          {stages && <MultiSelect label="Tournament stage" value={filters.stages} onChange={(v) => set({ stages: v })} options={lk.stages} searchable={false} />}
          {teams && <MultiSelect label="Team" value={filters.teams} onChange={(v) => set({ teams: v })} options={lk.teams} />}
          <label className="block"><span className="label">From</span><input type="date" className="field" min={lk.dateRange[0]} max={lk.dateRange[1]} value={filters.date_from ?? ""} onChange={(e) => set({ date_from: e.target.value || null })} /></label>
          <label className="block"><span className="label">To</span><input type="date" className="field" min={lk.dateRange[0]} max={lk.dateRange[1]} value={filters.date_to ?? ""} onChange={(e) => set({ date_to: e.target.value || null })} /></label>
          <div className="flex gap-2">
            <button className="btn" onClick={reset} disabled={!active}><RotateCcw size={14} />Reset</button>
            {download && <button className="btn btn-primary" onClick={dl}><Download size={14} />Filtered {download} (CSV)</button>}
          </div>
        </Row>
      )}
    </div>
  );
}
