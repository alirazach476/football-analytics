import { useApiQuery } from "../../api";
import { KpiCard, PageHeader } from "../../components/ui";
import ChartSection from "../../components/ChartSection";
import { Block, ComingSoonNote, Loading, T, n0, pick, useTable } from "./kit";

const COV = ["pct_lineups", "pct_events", "pct_man_of_match", "pct_attendance", "pct_referee", "pct_venue", "pct_goals_with_event", "pct_events_with_coordinates"].map((v) => [v, v.replace("pct_", "% ").replace(/_/g, " ")] as [string, string]);

export default function Overview() {
  const k = useApiQuery<any>("kpis").data; const dq = useApiQuery<any>("data_quality_score").data;
  const cov = useTable("coverage_report"); const up = useTable("upcoming_fixtures");
  return (
    <div>
      <PageHeader title="Football analytics: World Cup, Euro, Copa América, Nations League" subtitle="Men's national-team competitions only. Data from licensed/open datasets and Wikipedia (see the Data engineering page). Results are never invented; missing data stays empty." />
      {!k ? <Loading h={200} /> : <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        <KpiCard label="Competitions" value={k.competitions} />
        <KpiCard label="Editions with matches" value={k.editions_played} hint={`plus ${k.editions_upcoming} upcoming edition(s) not played yet`} />
        <KpiCard label="Matches played" value={n0(k.matches_played)} />
        <KpiCard label="Teams" value={k.teams} />
        <KpiCard label="Players" value={n0(k.players)} hint="after merging duplicate identities across sources" />
        <KpiCard label="Goals (recorded scores)" value={n0(k.goals)} />
        <KpiCard label="Match events" value={n0(k.events)} />
        <KpiCard label="Venues" value={k.venues} />
        <KpiCard label="Coming soon" value={k.matches_coming_soon} hint="scheduled fixtures kept in the data" accent="#eab308" />
        <KpiCard label="Data quality score" value={dq?.score == null ? "n/a" : `${Math.round(dq.score)}%`} hint={dq ? `${dq.passed} of ${dq.total} automated checks passed in the latest run (Pandera on Silver + dbt on Gold). It measures rule compliance, not completeness.` : undefined} />
      </div>}
      <Block title="Dataset coverage by edition">
        <ChartSection spec={{ id: "ov.coverage", params: [{ key: "measure", label: "Coverage measure", type: "select", options: COV, default: "pct_lineups" }] }} />
        {cov.isLoading ? <Loading /> : <T t={pick(cov.table, ["season_id", "expected_matches", "matches_in_dataset", "matches_played", "matches_coming_soon", "pct_lineups", "pct_events", "goal_events", "goal_events_with_player", "awards", "coverage_flag"])} filename="coverage" pageSize={12} />}
      </Block>
      <Block title="Coming soon">
        <ComingSoonNote n={up.rows.length} />
        <T t={pick(up.table, ["match_date", "season_id", "stage_name", "group_name", "home_team_name", "away_team_name", "venue_name", "venue_city", "status_label", "fixture_detail"])} filename="upcoming_fixtures" pageSize={15} empty="No upcoming fixtures." />
      </Block>
    </div>
  );
}
