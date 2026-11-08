"""Pre-compute the heavy API caches into FB_CACHE_DIR (run at image build time, with the warehouse reachable):  python -m fbplatform.api.warm"""
import time

from . import store


def main():
    for n in ("player_stats", "contribution_index", "team_country", "outcome_test", "goal_test", "shap_values", "standings"):
        t = time.time()
        getattr(store, n)()
        print(f"{n}: {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
