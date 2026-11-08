from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
REGISTRY_DIR = DATA / "registry"
AUDIT_DIR = DATA / "audit"
USER_AGENT = "fbplatform-research/0.1 (open-data audit; respects rate limits)"
