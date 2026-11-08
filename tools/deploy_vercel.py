"""Deploy the React front end to Vercel, proxying /api/* to the backend.

    python tools/deploy_vercel.py https://<user>-football-analytics.hf.space [--prod]

Writes frontend/vercel.json from the template (backend URL filled in) and runs `vercel deploy`. Needs `vercel login` (already done on this machine).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FE = Path(__file__).resolve().parents[1] / "frontend"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args or not args[0].startswith("https://"):
        sys.exit(__doc__)
    backend = args[0].rstrip("/")
    (FE / "vercel.json").write_text((FE / "vercel.template.json").read_text(encoding="utf-8").replace("__BACKEND_URL__", backend), encoding="utf-8")
    cmd = ["vercel", "deploy", "--yes"] + (["--prod"] if "--prod" in sys.argv else [])
    sys.exit(subprocess.run(cmd, cwd=FE, shell=sys.platform == "win32").returncode)


if __name__ == "__main__":
    main()
