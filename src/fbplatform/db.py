"""Warehouse connection settings (kept free of heavy imports so the slim hosted API can use it)."""
from __future__ import annotations

import os


def dsn() -> str:
    """Local Docker warehouse by default; a hosted Postgres (e.g. Neon) via DATABASE_URL, or via WH_* plus WH_SSLMODE=require."""
    g = os.environ.get
    if g("DATABASE_URL"):
        return g("DATABASE_URL")
    ssl = f" sslmode={g('WH_SSLMODE')}" if g("WH_SSLMODE") else ""
    return (f"host={g('WH_HOST', 'localhost')} port={g('WH_PORT', '5442')} user={g('WH_USER', 'football')} "
            f"password={g('WH_PASSWORD', 'football_local_dev')} dbname={g('WH_DB', 'football_dw')}{ssl}")
