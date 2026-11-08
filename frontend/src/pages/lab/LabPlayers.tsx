import { useState } from "react";
import { Callout, Tabs } from "../../components/ui";
import { MultiSelect, Row, Segmented, SearchBox, Slider } from "../../components/controls";
import { Charts, LabPage, useLab } from "./labkit";

export default function LabPlayers() {
  const [term, setTerm] = useState(""); const lab = useLab({ term }); const d = lab.data; const [tab, setTab] = useState("Top scorers & assists");
  const pool = d?.players ?? []; const [picked, setPicked] = useState<string[] | null>(null); const [radar, setRadar] = useState<string[] | null>(null);
  const [n, setN] = useState(20); const [mm, setMm] = useState(270); const [measure, setMeasure] = useState("goals"); const [pci, setPci] = useState(900);
  const sel = picked ?? (term ? [] : pool.slice(0, 2));
  const rp = d?.radarPlayers ?? []; const radarSel = (radar ?? ["Harry Kane", "Luka Modrić"].filter((x) => rp.includes(x)).concat(sel.filter((x) => rp.includes(x))).slice(0, 4)).filter((x) => rp.includes(x));
  return (
    <LabPage title="Player visualisations" teams={false} stages={false} download="players" sample={d?.sample}
      caption="Collected competitions only (not careers). Goals are goals linked to a player id (Nations League scorers are not linked). Assists exist only in editions with event-level data. Per-90 rates use only matches with known minutes. Position and age are known for a subset of players: others are omitted, never guessed.">
      <div className="card mb-6 grid gap-4 p-4 md:grid-cols-2"><SearchBox label="Find players (name contains)" value={term} onChange={(v) => { setTerm(v); setPicked(null); }} placeholder="e.g. Kane" />
        <MultiSelect label="Players" value={sel} onChange={setPicked} options={pool} /></div>
      <Tabs tabs={["Top scorers & assists", "Per 90 minutes", "Profile radar", "Trends", "Age & position", "Contribution index"]} value={tab} onChange={setTab} id="lp" />
      <div className="pt-6">
        {tab === "Top scorers & assists" && <><div className="mb-4 max-w-sm"><Slider label="How many players" value={n} onChange={setN} min={10} max={40} /></div><Charts specs={[{ id: "player.top_goals", fixed: { n } }, { id: "player.top_assists", fixed: { n } }]} /></>}
        {tab === "Per 90 minutes" && <><div className="mb-4 max-w-sm"><Slider label="Minimum known minutes" value={mm} onChange={setMm} min={90} max={1500} step={90} /></div><Charts specs={[{ id: "player.per90_goals", fixed: { min: mm } }, { id: "player.per90_assists", fixed: { min: mm } }]} /></>}
        {tab === "Profile radar" && <><div className="mb-4 max-w-2xl"><MultiSelect label="Players with event-level data (max 4)" value={radarSel} onChange={setRadar} options={rp} max={4} /></div>
          <Charts shared={{ players: radarSel }} specs={[{ id: "player.radar", shared: ["players"] }]} /></>}
        {tab === "Trends" && <><Row className="mb-4"><Segmented label="Measure" value={measure} onChange={setMeasure} options={["goals", "assists"]} /></Row>
          {sel.length || pool.length ? <Charts shared={{ players: sel.length ? sel : pool.slice(0, 2) }} specs={[{ id: "player.trends", shared: ["players"], fixed: { measure } }]} /> : <Callout tone="info">Pick players above.</Callout>}</>}
        {tab === "Age & position" && <Charts specs={[{ id: "player.age" }, { id: "player.position" }]} />}
        {tab === "Contribution index" && <><div className="mb-4 max-w-sm"><Slider label="Minimum known minutes" value={pci} onChange={setPci} min={270} max={3000} step={90} /></div><Charts specs={[{ id: "player.pci", fixed: { min: pci } }]} /></>}
      </div>
    </LabPage>
  );
}
