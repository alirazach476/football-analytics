import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Skeleton } from "./components/ui";

const pages = {
  Home: lazy(() => import("./pages/Home")), Hub: lazy(() => import("./pages/CompetitionHub")), Tournament: lazy(() => import("./pages/TournamentRoute")), Wc2030: lazy(() => import("./pages/Wc2030")), Fixtures: lazy(() => import("./pages/Fixtures")), MatchCenter: lazy(() => import("./pages/MatchCenter")),
  Overview: lazy(() => import("./pages/analytics/Overview")), Competition: lazy(() => import("./pages/analytics/Competition")), Teams: lazy(() => import("./pages/analytics/Teams")),
  Players: lazy(() => import("./pages/analytics/Players")), Matches: lazy(() => import("./pages/analytics/Matches")), Ml: lazy(() => import("./pages/analytics/MachineLearning")), Eng: lazy(() => import("./pages/analytics/Engineering")),
  LabComp: lazy(() => import("./pages/lab/LabCompetitions")), LabTeams: lazy(() => import("./pages/lab/LabTeams")), LabPlayers: lazy(() => import("./pages/lab/LabPlayers")), LabMatches: lazy(() => import("./pages/lab/LabMatches")),
  LabStats: lazy(() => import("./pages/lab/LabStatistics")), LabMl: lazy(() => import("./pages/lab/LabMl")), LabEng: lazy(() => import("./pages/lab/LabEngineering")),
};

export default function App() {
  return (
    <Layout>
      <Suspense fallback={<Skeleton h={420} />}>
        <Routes>
          <Route path="/" element={<pages.Home />} />
          <Route path="/competition/:comp" element={<pages.Hub />} />
          <Route path="/tournament/:slug" element={<pages.Tournament />} />
          <Route path="/wc-2030" element={<pages.Wc2030 />} />
          <Route path="/fixtures" element={<pages.Fixtures />} />
          <Route path="/match/:key" element={<pages.MatchCenter />} />
          <Route path="/analytics/overview" element={<pages.Overview />} />
          <Route path="/analytics/competition" element={<pages.Competition />} />
          <Route path="/analytics/teams" element={<pages.Teams />} />
          <Route path="/analytics/players" element={<pages.Players />} />
          <Route path="/analytics/matches" element={<pages.Matches />} />
          <Route path="/analytics/ml" element={<pages.Ml />} />
          <Route path="/analytics/engineering" element={<pages.Eng />} />
          <Route path="/lab/competitions" element={<pages.LabComp />} />
          <Route path="/lab/teams" element={<pages.LabTeams />} />
          <Route path="/lab/players" element={<pages.LabPlayers />} />
          <Route path="/lab/matches" element={<pages.LabMatches />} />
          <Route path="/lab/statistics" element={<pages.LabStats />} />
          <Route path="/lab/ml" element={<pages.LabMl />} />
          <Route path="/lab/engineering" element={<pages.LabEng />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}
