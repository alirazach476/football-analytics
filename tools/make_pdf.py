"""Render tools/pdf/project_guide.html to docs/Football_Analytics_Project_Guide.pdf with headless Microsoft Edge (or Chrome).

    python tools/make_pdf.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "pdf" / "project_guide.html"
OUT = ROOT / "docs" / "Football_Analytics_Project_Guide.pdf"
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe", "/usr/bin/google-chrome", "/usr/bin/chromium"]


def main():
    exe = next((b for b in BROWSERS if Path(b).exists()), None)
    if not exe:
        sys.exit("no Edge/Chrome found")
    with tempfile.TemporaryDirectory() as prof:
        subprocess.run([exe, "--headless=new", "--disable-gpu", f"--user-data-dir={prof}", "--no-pdf-header-footer", f"--print-to-pdf={OUT}", SRC.as_uri()], check=True, timeout=180)
    print(f"{OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
