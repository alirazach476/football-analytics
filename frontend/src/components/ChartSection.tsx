import { useMemo, useState } from "react";
import { useChartData, useLookups } from "../api";
import { useFilters } from "../state/filters";
import ChartCard, { PickedPoint } from "./ChartCard";
import { MultiSelect, Opt, Row, Segmented, SelectField, Slider, Toggle } from "./controls";

export interface Ctl {
  key: string; label: string; type: "segmented" | "select" | "toggle" | "slider" | "multi";
  options?: Opt[]; optionsFrom?: "teams" | "seasons" | "models" | "shotSeasons"; default?: any; min?: number; max?: number; step?: number; maxSelect?: number;
}
export interface ChartSpec {
  id: string; title?: string; params?: Ctl[]; shared?: string[]; fixed?: Record<string, any>; height?: number;
  cross?: { field: "x" | "customdata0" | string; set: string; mode?: "replace" | "add" }; hint?: string; filtersOverride?: any;
}
export type Shared = Record<string, any>;

export function useOptions(from?: Ctl["optionsFrom"]): Opt[] | undefined {
  const { data } = useLookups();
  return useMemo(() => {
    if (!from || !data) return undefined;
    if (from === "teams") return data.teams;
    if (from === "seasons") return data.seasons.map((s) => s.seasonId);
    if (from === "models") return data.models;
    return data.shotMapSeasons;
  }, [from, data]);
}

export function Control({ c, value, onChange }: { c: Ctl; value: any; onChange: (v: any) => void }) {
  const opts = useOptions(c.optionsFrom) ?? c.options ?? [];
  switch (c.type) {
    case "segmented": return <Segmented label={c.label} value={value} onChange={onChange} options={opts} />;
    case "select": return <SelectField label={c.label} value={value} onChange={onChange} options={opts} />;
    case "toggle": return <Toggle label={c.label} value={!!value} onChange={onChange} />;
    case "slider": return <Slider label={c.label} value={Number(value)} onChange={onChange} min={c.min ?? 0} max={c.max ?? 100} step={c.step} />;
    case "multi": return <MultiSelect label={c.label} value={value ?? []} onChange={onChange} options={opts} max={c.maxSelect} />;
  }
}

export default function ChartSection({ spec, shared = {}, setShared, enabled = true }: { spec: ChartSpec; shared?: Shared; setShared?: (p: Shared) => void; enabled?: boolean }) {
  const { filters } = useFilters();
  const f = spec.filtersOverride ?? filters;
  const [local, setLocal] = useState<Record<string, any>>(() => Object.fromEntries((spec.params ?? []).map((c) => [c.key, c.default])));
  const params = useMemo(() => ({ ...(spec.fixed ?? {}), ...local, ...Object.fromEntries((spec.shared ?? []).map((k) => [k, shared[k]])) }), [spec, local, shared]);
  const ready = enabled && (spec.shared ?? []).every((k) => shared[k] !== undefined && shared[k] !== null && shared[k] !== "");
  const q = useChartData(spec.id, f, params, ready);
  const onSelect = spec.cross && setShared ? (pts: PickedPoint[]) => {
    const vals = pts.map((p) => {
      if (spec.cross!.field === "x") return p.x;
      if (spec.cross!.field === "customdata0") return (Array.isArray(p.customdata) ? p.customdata[0] : p.customdata) ?? p.x;
      if (spec.cross!.field.startsWith("row:")) return q.data?.data.rows[p.pointIndex]?.[spec.cross!.field.slice(4)];
      return undefined;
    }).filter((v) => v !== undefined && v !== null);
    if (!vals.length) return;
    const key = spec.cross!.set;
    setShared({ [key]: spec.cross!.mode === "add" ? Array.from(new Set([...(shared[key] ?? []), ...vals])).slice(-6) : vals[vals.length - 1] });
  } : undefined;
  return (
    <div className="mb-6">
      {spec.title && <h3 className="mb-2 font-display text-base font-bold">{spec.title}</h3>}
      {(spec.params?.length ?? 0) > 0 && <Row className="mb-3">{spec.params!.map((c) => <Control key={c.key} c={c} value={local[c.key]} onChange={(v) => setLocal((s) => ({ ...s, [c.key]: v }))} />)}</Row>}
      {spec.hint && <p className="mb-2 text-xs" style={{ color: "var(--c-muted)" }}>{spec.hint}</p>}
      {!ready ? <div className="chart-card p-5 text-sm text-slate-600">Choose a value above to draw this chart.</div>
        : <ChartCard payload={q.data} loading={q.isFetching} error={q.error} title={spec.title} onSelect={onSelect} exportInfo={{ id: spec.id, filters: f, params }} height={spec.height} />}
    </div>
  );
}
