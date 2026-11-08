"""Serve the API from this PC through a free Cloudflare quick tunnel and (re)deploy the Vercel front end pointing at it.

    python tools/serve_public.py                 # API on the local Docker warehouse (docker compose up -d first)
    python tools/serve_public.py --neon          # API on the hosted Neon database (set FOOTBALL_DATABASE_URL)
    python tools/serve_public.py --no-vercel     # only start API + tunnel and print the public URL

A quick tunnel gets a NEW address every run, so the Vercel deployment is rebuilt with that address (frontend/vercel.json rewrites /api/* to it).
The site works only while this script is running. Stop with Ctrl+C.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("PORT", "8010"))
CLOUDFLARED = next((p for p in (r"C:\Program Files (x86)\cloudflared\cloudflared.exe", r"C:\Program Files\cloudflared\cloudflared.exe", "cloudflared") if p == "cloudflared" or Path(p).exists()), "cloudflared")


def wait_health(url: str, tries: int = 60) -> bool:
    for _ in range(tries):
        try:
            if b'"ok":true' in urllib.request.urlopen(url + "/api/health", timeout=10).read().replace(b" ", b""):
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


def main():
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "MLFLOW_DISABLE_AGENT_HINT": "1", "FB_CACHE_DIR": str(ROOT / "deploy" / "cache")}
    if "--neon" in sys.argv:
        if not os.environ.get("FOOTBALL_DATABASE_URL"):
            sys.exit("set FOOTBALL_DATABASE_URL to the Neon connection string")
        env["DATABASE_URL"] = os.environ["FOOTBALL_DATABASE_URL"]
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "fbplatform.api.main:app", "--host", "127.0.0.1", "--port", str(PORT)], env=env, cwd=ROOT)
    tun = subprocess.Popen([CLOUDFLARED, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PORT}"], stderr=subprocess.PIPE, text=True)
    try:
        public = None
        for line in tun.stderr:                                            # cloudflared logs the quick-tunnel address on stderr
            m = next((u for u in re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", line) if not u.startswith("https://api.")), None)   # cloudflared also logs its own api.trycloudflare.com
            if m:
                public = m
                break
        if not public:
            sys.exit("could not read the tunnel address from cloudflared")
        print("tunnel:", public, flush=True)
        if not wait_health(public):
            sys.exit("API not reachable through the tunnel")
        print("API healthy through the tunnel", flush=True)
        if "--no-vercel" not in sys.argv:
            subprocess.run([sys.executable, str(ROOT / "tools" / "deploy_vercel.py"), public, "--prod"], check=True)
        print("running: keep this window open; Ctrl+C to stop", flush=True)
        api.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for p in (tun, api):
            p.terminate()


if __name__ == "__main__":
    main()
