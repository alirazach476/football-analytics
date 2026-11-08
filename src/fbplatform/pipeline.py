"""Run every stage in dependency order. Each stage is resumable (HTTP cache + per-match checkpoints).

    python -m fbplatform.pipeline            # full run
Order matters: `build` regenerates matches.parquet, `teams` then adds team ids to it.
"""
from __future__ import annotations

import logging
import time

from .config import DATA

log = logging.getLogger("fbplatform.pipeline")


def main():
    (DATA / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(DATA / "logs" / "pipeline.log", encoding="utf-8")])
    from .audit import run as audit
    from .ingest import wikipedia as wikipedia_fetch
    from .ingest import es_wikipedia, squads, venues
    from .ingest import build, fjelstul, goals, martj42, quality, stats, statsbomb_events, teams, unify, wikipedia_matches, wyscout
    for name, fn in (("audit", audit), ("matches", build.run), ("martj42 matches + cross-check", martj42.run),
                     ("wikipedia pages (API, cached)", wikipedia_fetch.run), ("teams", teams.run),
                     ("wikipedia: enrich + goals", wikipedia_matches.enrich_and_goals),
                     ("statsbomb events/lineups/players", statsbomb_events.run), ("stats", stats.run),
                     ("openfootball goal events", goals.run), ("wyscout (Euro 2016 events)", wyscout.run), ("fjelstul (World Cup 2002-22)", fjelstul.run),
                     ("attendance from es.wikipedia (fill-null)", es_wikipedia.run), ("venues", venues.build),
                     ("unify providers", unify.run), ("squads (Wikipedia) + player linking", squads.stage), ("quality", quality.run)):
        t0 = time.time()
        try:
            fn()
        except Exception:
            log.exception("stage '%s' FAILED - fix and re-run; completed work is checkpointed", name)
            raise
        log.info("stage '%s' done in %.1fs", name, time.time() - t0)


if __name__ == "__main__":
    main()
