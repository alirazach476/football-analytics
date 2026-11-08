import { useQuery } from "@tanstack/react-query";

export interface Table { columns: string[]; rows: Record<string, any>[]; total: number }
export interface ChartPayload {
  name: string; available: boolean; reason: string; n: number; unit: string; source: string; note: string; hasStatic: boolean;
  data: Table; figure: { data: any[]; layout: any } | null;
}
export interface Filters { competitions: string[]; seasons: string[]; stages: string[]; teams: string[]; date_from?: string | null; date_to?: string | null }
export const EMPTY_FILTERS: Filters = { competitions: [], seasons: [], stages: [], teams: [], date_from: null, date_to: null };

async function http<T>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, body === undefined ? undefined : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).error ?? msg; } catch { /* ignore */ }
    throw new Error(msg);
  }
  return r.json();
}
export const chartRequest = (id: string, filters: Filters, params: Record<string, any>) => http<ChartPayload>("/api/chart", { id, filters, params });
export const queryRequest = <T = any>(name: string, args: Record<string, any> = {}) => http<T>("/api/query", { name, args });
export async function downloadExport(id: string, filters: Filters, params: Record<string, any>, format: "csv" | "html" | "png", filename: string) {
  const r = await fetch("/api/export", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id, filters, params, format }) });
  if (!r.ok) throw new Error((await r.json().catch(() => ({ error: r.statusText }))).error);
  saveBlob(await r.blob(), `${filename}.${format}`);
}
export function saveBlob(blob: Blob, name: string) {
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

const STALE = 5 * 60 * 1000;
export const useChartData = (id: string, filters: Filters, params: Record<string, any>, enabled = true) =>
  useQuery({ queryKey: ["chart", id, filters, params], queryFn: () => chartRequest(id, filters, params), enabled, staleTime: STALE, placeholderData: (p) => p });
export const useApiQuery = <T = any>(name: string, args: Record<string, any> = {}, enabled = true) =>
  useQuery({ queryKey: ["q", name, args], queryFn: () => queryRequest<T>(name, args), enabled, staleTime: STALE });

export interface Edition {
  seasonId: string; slug: string; themeKey: string; competition: "WC" | "EURO" | "COPA" | "UNL"; competitionName: string; edition: string; year: number; host: string | null; start: string | null; end: string | null;
  teams: number | null; format: string | null; verification: string | null; status: "in_data" | "upcoming" | "announced"; matchesPlayed: number; matchesComingSoon: number; champion: string | null; runnerUp: string | null;
}
export interface Lookups {
  competitions: { id: string; label: string; color: string }[]; seasons: { seasonId: string; competition: string; year: number; status: string }[]; teams: string[]; stages: string[];
  dateRange: [string, string]; reliableAssistSeasons: string[]; shotMapSeasons: string[]; models: string[];
}
export const useLookups = () => useQuery({ queryKey: ["lookups"], queryFn: () => http<Lookups>("/api/lookups"), staleTime: Infinity });
export const useTournaments = () => useQuery({ queryKey: ["tournaments"], queryFn: () => http<{ editions: Edition[]; wc2030: any }>("/api/tournaments"), staleTime: STALE });
export const useTournament = (season: string) => useQuery({ queryKey: ["tournament", season], queryFn: () => http<any>(`/api/tournament/${season}`), staleTime: STALE });
export const useWc2030 = () => useQuery({ queryKey: ["wc2030"], queryFn: () => http<{ facts: any; sources: { label: string; url: string }[] }>("/api/wc2030"), staleTime: Infinity });
export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: () => http<{ ok: boolean; database: string; message: string | null }>("/api/health"), refetchInterval: 30000, retry: 0 });
export const predict = (body: Record<string, any>) => http<any>("/api/ml/predict", body);
export const matchDetail = (key: number) => http<any>(`/api/matches/${key}`);
