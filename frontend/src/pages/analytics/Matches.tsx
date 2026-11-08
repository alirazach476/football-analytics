import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, Radio } from "lucide-react";
import { useApiQuery } from "../../api";
import { Callout, Section } from "../../components/ui";
import { SelectField, Toggle } from "../../components/controls";
import ChartSection from "../../components/ChartSection";
import FixtureCard from "../../components/match/FixtureCard";
import { MatchRow } from "../../components/match/matchUtils";
import { MatchCenterView } from "../MatchCenter";
import { Loading, useTable } from "./kit";

/** Match analytics as a broadcast hub: pick filters, flick through scoreboard cards, and the full Match Center (scoreboard, statistics, line-ups, events, head-to-head) opens below. */
export default function Matches() {
  const seasons = useApiQuery<string[]>("season_ids").data ?? []; const teams = useApiQuery<string[]>("team_names").data ?? [];
  const [sp, setSp] = useSearchParams(); const [season, setSeason] = useState("WC-2022"); const [team, setTeam] = useState(""); const [upcoming, setUpcoming] = useState(true);
  const res = useTable("match_search", { season: season || null, team: team || null, include_upcoming: upcoming });
  const rows: MatchRow[] = useMemo(() => res.rows.map((r) => ({ ...r, competition_id: String(r.season_id).split("-")[0], is_played: r.status_label !== "Coming soon", went_beyond_90: null, had_shootout: null } as MatchRow)), [res.rows]);
  const fromUrl = sp.get("mk"); const [mk, setMk] = useState<string>();
  useEffect(() => { if (fromUrl) { setMk(fromUrl); setSeason(""); } }, [fromUrl]);
  const cur = mk ?? (rows.find((r) => r.is_played) ?? rows[0])?.match_key?.toString();
  const rail = useRef<HTMLDivElement>(null);
  const scroll = (d: number) => rail.current?.scrollBy({ left: d * 340, behavior: "smooth" });
  return (
    <div>
      <header className="mb-6">
        <div className="mb-1 inline-flex items-center gap-2 px-3 py-0.5 text-[11px] font-bold uppercase tracking-[0.22em]" style={{ background: "var(--c-primary)", color: "var(--c-on-primary)", clipPath: "polygon(0 0, 100% 0, 96% 100%, 0 100%)" }}><Radio size={12} />Match analytics</div>
        <h1 className="display-caps text-4xl font-bold leading-tight sm:text-6xl">Match <span style={{ color: "var(--c-primary)" }}>Center</span></h1>
        <p className="mt-2 max-w-3xl text-sm" style={{ color: "var(--c-muted)" }}>Choose an edition or a team, pick a match from the scoreboard rail and open its full broadcast view: events, statistics, line-ups on the pitch and head-to-head.</p>
      </header>
      <div className="card mb-5 flex flex-wrap items-end gap-4 p-4">
        <SelectField label="Edition" value={season} onChange={(v) => { setSeason(v); setMk(undefined); setSp({}); }} options={[["", "All editions"], ...seasons.map((s) => [s, s] as [string, string])]} />
        <SelectField label="Team" value={team} onChange={(v) => { setTeam(v); setMk(undefined); setSp({}); }} options={[["", "Any team"], ...teams.map((s) => [s, s] as [string, string])]} />
        <Toggle label="Include 'Coming soon' fixtures" value={upcoming} onChange={setUpcoming} />
        <span className="ml-auto text-xs" style={{ color: "var(--c-muted)" }}>{rows.length} matches · most recent first (max 200)</span>
      </div>

      {res.isLoading ? <Loading h={200} /> : !rows.length && !fromUrl ? <Callout tone="info">No matches for this filter.</Callout> : <>
        {rows.length > 0 && <div className="relative mb-8">
          <button className="btn absolute -left-2 top-1/2 z-10 -translate-y-1/2 !rounded-full !p-2 shadow-xl" onClick={() => scroll(-1)} aria-label="Scroll matches left"><ChevronLeft size={18} /></button>
          <div ref={rail} className="no-scrollbar flex snap-x gap-4 overflow-x-auto px-1 py-3">
            {rows.slice(0, 60).map((m) => <div key={m.match_key} className="w-[310px] shrink-0 snap-start"><FixtureCard m={m} showComp={false} onSelect={(x) => { setMk(String(x.match_key)); setSp({}); }} selected={String(m.match_key) === cur} /></div>)}
          </div>
          <button className="btn absolute -right-2 top-1/2 z-10 -translate-y-1/2 !rounded-full !p-2 shadow-xl" onClick={() => scroll(1)} aria-label="Scroll matches right"><ChevronRight size={18} /></button>
        </div>}
        {cur && <MatchCenterView key={cur} matchKey={cur} embedded />}
        {cur && <Section title="Goal timing in this edition" hint="When goals were scored across the whole edition of the selected match."><EditionGoals matchKey={cur} /></Section>}
      </>}
    </div>
  );
}

function EditionGoals({ matchKey }: { matchKey: string }) {
  const m = useTable("match_row", { match_key: Number(matchKey) }).rows[0];
  if (!m) return null;
  return <ChartSection key={m.season_id} spec={{ id: "an.goal_minutes", fixed: { comp: m.competition_id, season: m.season_id } }} />;
}
