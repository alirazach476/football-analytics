import { lazy, Suspense } from "react";
import { useParams } from "react-router-dom";
import { Skeleton } from "../components/ui";

const TournamentPage = lazy(() => import("./TournamentPage"));
const FinalissimaPage = lazy(() => import("./FinalissimaPage"));

/** /tournament/:slug: the Finalissima (a separate, curated section) has its own page; every other edition comes from the warehouse. */
export default function TournamentRoute() {
  const { slug = "" } = useParams();
  return <Suspense fallback={<Skeleton h={480} />}>{slug.toLowerCase().startsWith("fin-") ? <FinalissimaPage key={slug} slug={slug.toLowerCase()} /> : <TournamentPage />}</Suspense>;
}
