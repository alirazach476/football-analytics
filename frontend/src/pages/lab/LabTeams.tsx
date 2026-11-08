import { useEffect, useRef, useState } from "react";
import { Callout, Tabs } from "../../components/ui";
import { MultiSelect, Row, SelectField, Slider } from "../../components/controls";
import { Charts, LabPage, useLab, useShared } from "./labkit";

export default function LabTeams() {
  const lab = useLab(); const names = lab.data?.teams ?? []; const [tab, setTab] = useState("Results");
  const [sh, setSh] = useShared({ teams: [] as string[] }); const touched = useRef(false);
  const [a, setA] = useState<string>(); const [b, setB] = useState<string>(); const [mn, setMn] = useState(15);
  useEffect(() => { if (!names.length) return; const keep = (sh.teams as string[]).filter((t) => names.includes(t));
    if (!touched.current && !keep.length) setSh({ teams: ["Argentina", "France", "Spain"].filter((t) => names.includes(t)).concat(names).slice(0, 3).filter((t, i, arr) => arr.indexOf(t) === i) });
    else if (keep.length !== sh.teams.length) setSh({ teams: keep }); }, [names.join("|")]); // eslint-disable-line
  const sel: string[] = sh.teams ?? [];
  const A = a && names.includes(a) ? a : sel[0] ?? names[0], B = b && names.includes(b) ? b : sel[1] ?? names[Math.min(1, names.length - 1)];
  return (
    <LabPage title="Team visualisations" teams={false} sample={lab.data?.sample} caption="Result = recorded score (extra time included, shoot-outs excluded). Only matches in the four collected competitions: these are not full national-team records.">
      {!names.length ? <Callout tone="info">No team has matches in the current filters.</Callout> : <>
        <div className="mb-5 max-w-2xl"><MultiSelect label="Teams to highlight / compare (also set by clicking a bubble on the scatter in the Results tab)" value={sel} onChange={(v) => { touched.current = true; setSh({ teams: v }); }} options={names} max={6} /></div>
        <Tabs tabs={["Results", "Profile", "History", "Head-to-head", "Rankings & consistency"]} value={tab} onChange={setTab} id="lt" />
        <div className="pt-6">
          {tab === "Results" && <Charts shared={sh} setShared={(p) => { touched.current = true; setSh(p); }} specs={[
            { id: "team.wdl", shared: ["teams"], fixed: { top_n: 20, min_matches: 10 } },
            { id: "team.gfga", fixed: { min_matches: 15 }, cross: { field: "row:team_name", set: "teams", mode: "add" }, hint: "Click bubbles to add teams to the selection used by the profile, heat-map and timeline tabs." }]} />}
          {tab === "Profile" && <Charts shared={sh} specs={[{ id: "team.radar", shared: ["teams"] }, { id: "team.heat", shared: ["teams"] }]} />}
          {tab === "History" && <Charts shared={sh} specs={[{ id: "team.timeline", shared: ["teams"] }, { id: "team.edheat", shared: ["teams"] }]} />}
          {tab === "Head-to-head" && <>
            <Row className="mb-4"><SelectField label="Team A" value={A} onChange={setA} options={names} /><SelectField label="Team B" value={B} onChange={setB} options={names} /></Row>
            <Charts shared={{ a: A, b: B }} specs={[{ id: "team.h2h_summary", shared: ["a", "b"] }, { id: "team.h2h_timeline", shared: ["a", "b"] }]} />
          </>}
          {tab === "Rankings & consistency" && <>
            <div className="mb-4 max-w-sm"><Slider label="Minimum matches for a team to be ranked" value={mn} onChange={setMn} min={5} max={40} /></div>
            <Charts specs={[{ id: "team.rank", fixed: { min: mn } }, { id: "team.cons" }]} />
          </>}
        </div>
      </>}
    </LabPage>
  );
}
