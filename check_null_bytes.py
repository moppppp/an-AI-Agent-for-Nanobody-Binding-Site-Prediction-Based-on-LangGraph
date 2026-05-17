from pathlib import Path

ROOT = Path(__file__).resolve().parent
NULL = b"\x00"

bad = []
for path in sorted(ROOT.rglob("*.py")):
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        bad.append((path, "UTF-16 BOM"))
    elif NULL in data:
        bad.append((path, f"nulls={data.count(NULL)}"))

if not bad:
    print("OK: all .py files are UTF-8")
else:
    print("BAD files:")
    for path, msg in bad:
        print(f"  {path} ({msg})")
