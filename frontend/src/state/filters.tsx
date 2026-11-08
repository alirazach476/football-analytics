import { createContext, useContext, useEffect, useMemo, useState, ReactNode } from "react";
import { EMPTY_FILTERS, Filters } from "../api";

interface Ctx { filters: Filters; set: (p: Partial<Filters>) => void; reset: () => void; active: boolean }
const FilterCtx = createContext<Ctx>({ filters: EMPTY_FILTERS, set: () => {}, reset: () => {}, active: false });
const KEY = "fa.filters.v1";

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<Filters>(() => { try { return { ...EMPTY_FILTERS, ...JSON.parse(localStorage.getItem(KEY) || "{}") }; } catch { return EMPTY_FILTERS; } });
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify(filters)); } catch { /* storage unavailable */ } }, [filters]);
  const value = useMemo<Ctx>(() => ({
    filters, set: (p) => setFilters((f) => ({ ...f, ...p })), reset: () => setFilters(EMPTY_FILTERS),
    active: filters.competitions.length + filters.seasons.length + filters.stages.length + filters.teams.length > 0 || !!filters.date_from || !!filters.date_to,
  }), [filters]);
  return <FilterCtx.Provider value={value}>{children}</FilterCtx.Provider>;
}
export const useFilters = () => useContext(FilterCtx);

export function describeFilters(f: Filters): string {
  const b: string[] = [];
  if (f.competitions.length) b.push(f.competitions.join(", "));
  if (f.seasons.length) b.push(`${f.seasons.length} edition(s)`);
  if (f.stages.length) b.push(f.stages.join(", "));
  if (f.teams.length) b.push(f.teams.slice(0, 3).join(", ") + (f.teams.length > 3 ? "…" : ""));
  if (f.date_from || f.date_to) b.push(`${f.date_from ?? "…"} → ${f.date_to ?? "…"}`);
  return b.join(" · ") || "no filters";
}
