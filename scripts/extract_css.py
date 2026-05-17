import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "scripts" / "gen_web_static.py").read_text(encoding="utf-8")
m = re.search(r'APP_CSS = """(.*?)"""', src, re.DOTALL)
if not m:
    raise SystemExit("APP_CSS not found")
(ROOT / "web" / "static").mkdir(parents=True, exist_ok=True)
(ROOT / "web" / "static" / "app.css").write_bytes(m.group(1).encode("utf-8"))
print("wrote app.css", len(m.group(1)))
