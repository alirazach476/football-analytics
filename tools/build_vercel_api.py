"""Assemble the serverless API bundle (Vercel Python function) in build/vercel_api, ready for `vercel deploy --prod`.

The function runs the same FastAPI app as the local server; it reads the warehouse from DATABASE_URL (Neon) and the heavy ML caches from deploy/cache.

    PYTHONPATH=src python tools/prepare_render.py        # once, to refresh caches / silver pickles
    python tools/build_vercel_api.py
    cd build/vercel_api && vercel deploy --prod --yes     # first time: vercel link --yes --project football-analytics-api; vercel env add DATABASE_URL production
"""
from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "vercel_api"
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "*.tmp")

INDEX = '''"""Vercel entry point: the FastAPI app of the project (ASGI)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("FB_CACHE_DIR", str(ROOT / "deploy" / "cache"))
os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")
os.environ.setdefault("MPLBACKEND", "Agg")

from fbplatform.api.main import app  # noqa: E402,F401
'''

VERCEL_JSON = '''{
  "functions": { "api/index.py": { "maxDuration": 60, "memory": 1024, "excludeFiles": "{**/tests/**,**/test/**,**/__pycache__/**,**/*.pyc,**/*.md}" } },
  "routes": [ { "src": "/(.*)", "dest": "/api/index.py" } ]
}
'''


def main():
    if OUT.exists():
        shutil.rmtree(OUT, onexc=lambda fn, path, exc: (os.chmod(path, stat.S_IWRITE), fn(path)))
    (OUT / "api").mkdir(parents=True)
    (OUT / "api" / "index.py").write_text(INDEX, encoding="utf-8")
    (OUT / "vercel.json").write_text(VERCEL_JSON, encoding="utf-8")
    shutil.copy2(ROOT / "deploy" / "vercel" / "requirements.txt", OUT / "requirements.txt")
    (OUT / ".vercelignore").write_text("*.log\n", encoding="utf-8")
    shutil.copytree(ROOT / "src", OUT / "src", ignore=IGNORE)
    for d in ("models", "reports", "sql"):
        shutil.copytree(ROOT / d, OUT / d, ignore=IGNORE)
    data = OUT / "data"
    shutil.copytree(ROOT / "data" / "registry", data / "registry")
    shutil.copytree(ROOT / "data" / "silver_pkl", data / "silver_pkl")
    shutil.copy2(ROOT / "data" / "layer_counts_snapshot.json", data / "layer_counts_snapshot.json")
    shutil.copytree(ROOT / "deploy" / "cache", OUT / "deploy" / "cache")
    mb = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file()) / 1e6
    print(f"bundle ready: {OUT} ({mb:.0f} MB of project files; libraries are installed by Vercel from requirements.txt)")


if __name__ == "__main__":
    sys.exit(main())
