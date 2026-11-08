import { useState } from "react";
import { Callout, Tabs } from "../../components/ui";
import { Row, Segmented, SelectField, Slider } from "../../components/controls";
import { Charts, LabPage, useLab } from "./labkit";

const SHOT_SEASONS = ["WC-2018", "WC-2022", "EURO-2016", "EURO-2020", "EURO-2024", "COPA-2024"];

export default function LabMatches() {
  const [shotSeason, setShotSeason] = useState("WC-2022"); const lab = useLab({ matches: true, shotSeason }); const d = lab.data; const [tab, setTab] = useState("Single match");
  const [mk, setMk] = useState<string>(); const [team, setTeam] = useState<string>(); const [upto, setUpto] = useState(60); const [shotTeam, setShotTeam] = useState<string>(); const [by, setBy] = useState("competition_id");
  const ms = d?.matches ?? []; const firstPlayed = ms.find((m) => m.played) ?? ms[0];
  const cur = ms.find((m) => String(m.key) === mk) ?? firstPlayed;
  const net = cur && (team === cur.home || team === cur.away) ? team : cur?.home;
  const st = d?.shotTeams ?? []; const stCur = shotTeam && st.includes(shotTeam) ? shotTeam : st[0];
  const m = cur ? { match_key: cur.key } : {};
  return (
    <LabPage title="Match visualisations" sample={d?.sample} caption="Event-level charts are drawn only from data that exists: shot maps need shot coordinates (StatsBomb/Wyscout matches), passing networks need recorded pass recipients (StatsBomb), score progression must reproduce the final score. Otherwise the chart says why it is not shown.">
      <Tabs tabs={["Single match", "Shots (maps)", "Distributions", "Home / away", "Penalty shoot-outs"]} value={tab} onChange={setTab} id="lm" />
      <div className="pt-6">
        {tab === "Single match" && (!cur ? <Callout tone="info">No matches in the current filters.</Callout> : <>
          <div className="mb-4 max-w-3xl"><SelectField label="Match (most recent 400 in the filters; 'COMING SOON' = not played yet)" value={String(cur.key)} onChange={setMk} options={ms.map((x) => [String(x.key), x.label] as [string, string])} /></div>
          {!cur.played ? <Callout tone="soon" title="Coming soon">{cur.fixtureDetail}. No result and no events exist yet.</Callout> : <>
            <p className="mb-4 text-sm font-semibold">{cur.label}</p>
            <Charts shared={m} specs={[{ id: "match.goal_timeline", shared: ["match_key"] }, { id: "match.progress", shared: ["match_key"] }, { id: "match.events", shared: ["match_key"] }, { id: "match.shots_match", shared: ["match_key"] }]} />
            <Row className="mb-4"><Segmented label="Passing network for" value={net} onChange={setTeam} options={[cur.home, cur.away]} />
              <div className="min-w-[14rem]"><Slider label="Use passes up to minute" value={upto} onChange={setUpto} min={15} max={120} /></div></Row>
            <p className="mb-3 text-xs" style={{ color: "var(--c-muted)" }}>Before the first substitution the network shows the starting players only.</p>
            <Charts shared={{ ...m, team: net, upto }} specs={[{ id: "match.net", shared: ["match_key", "team", "upto"] }]} />
          </>}</>)}
        {tab === "Shots (maps)" && <>
          <Row className="mb-4"><SelectField label="Edition (only these have shot coordinates)" value={shotSeason} onChange={(v) => { setShotSeason(v); setShotTeam(undefined); }} options={SHOT_SEASONS} />
            <SelectField label="Team" value={stCur} onChange={setShotTeam} options={st} /></Row>
          {stCur && <Charts shared={{ season: shotSeason, team: stCur }} specs={[{ id: "match.shots_team", shared: ["season", "team"] }]} />}
        </>}
        {tab === "Distributions" && <>
          <Charts specs={[{ id: "match.scoreline" }]} />
          <Row className="mb-4"><Segmented label="Group outcomes by" value={by} onChange={setBy} options={[["competition_id", "Competition"], ["season_id", "Edition"], ["stage_name", "Stage"]]} /></Row>
          <Charts specs={[{ id: "match.outcome", fixed: { by } }]} />
        </>}
        {tab === "Home / away" && <Charts specs={[{ id: "match.homeaway" }]} />}
        {tab === "Penalty shoot-outs" && <Charts specs={[{ id: "match.so_edition" }, { id: "match.so_scores" }, { id: "match.so_records" }]} />}
      </div>
    </LabPage>
  );
}
