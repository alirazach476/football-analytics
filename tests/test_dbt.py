import subprocess
from pathlib import Path
import psycopg
import pytest
from fbplatform.warehouse.load import dsn

try:
    psycopg.connect(dsn(), connect_timeout=3).close()
    UP = True
except Exception:
    UP = False

DBT = Path(__file__).resolve().parents[1] / "dbt" / "football_dbt"


@pytest.mark.skipif(not UP, reason="warehouse not running")
def test_dbt_build_all_models_and_tests_pass():
    r = subprocess.run(["dbt", "build", "--profiles-dir", "."], cwd=DBT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-1000:]
    assert "WARN=0" in r.stdout and "ERROR=0" in r.stdout, r.stdout[-1500:]
