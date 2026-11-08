"""Rebuild every derived table from the data already downloaded (no network, no audit): one command, one process.

    python -m fbplatform.rebuild

Use `python -m fbplatform.pipeline` instead when new pages / datasets must be fetched first.
A lock file stops two rebuilds from writing the same tables at the same time.
"""
from __future__ import annotations

import logging
import os
import sys
import time

from .config import DATA

LOCK = DATA / "rebuild.lock"
log = logging.getLogger("fbplatform.rebuild")


def main():
    (DATA / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(DATA / "logs" / "pipeline.log", encoding="utf-8")])
    if LOCK.exists():
        log.error("another rebuild is running (lock file %s, started %s). Remove the file only if you are sure it is stale.",
                  LOCK, LOCK.read_text())
        sys.exit(2)
    LOCK.write_text(f"pid {os.getpid()} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        from .ingest import (build, es_wikipedia, fjelstul, goals, martj42, quality, squads, stats, statsbomb_events, teams, unify, venues, wikipedia_matches,
                             wikipedia_validation, wyscout)
        from .registry import write_registry
        for name, fn in (("registry", write_registry), ("matches", build.run), ("martj42", martj42.run), ("teams", teams.run),
                         ("wikipedia enrich + goals + details", wikipedia_matches.enrich_and_goals),
                         ("statsbomb combine", statsbomb_events.combine), ("stats", stats.run), ("openfootball goals", goals.run),
                         ("wyscout", wyscout.run), ("fjelstul", fjelstul.run),
                         ("attendance from es.wikipedia (fill-null)", es_wikipedia.run), ("venues", venues.build),
                         ("wikipedia validation", wikipedia_validation.run),
                         ("unify", unify.run), ("squads", squads.stage), ("quality", quality.run)):
            t0 = time.time()
            fn()
            log.info("stage '%s' done in %.1fs", name, time.time() - t0)
    finally:
        LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
