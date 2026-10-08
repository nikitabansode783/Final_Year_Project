from pathlib import Path

ROOT = Path(__file__).resolve().parent
main = ROOT / "main.py"
router_file = ROOT / "live_environment.py"

if not main.exists():
    raise SystemExit(f"Could not find {main}")

text = main.read_text(encoding="utf-8")

import_line = "from backend.live_environment import router as live_environment_router"
include_line = "app.include_router(live_environment_router)"

changed = False

if import_line not in text:
    text = import_line + "\n" + text
    changed = True

if include_line not in text:
    text += "\n\n" + include_line + "\n"
    changed = True

main.write_text(text, encoding="utf-8")

print("LIVE ENVIRONMENT FEATURE INSTALLED")
print(f"Router file: {router_file}")
print(f"Main file:   {main}")
print("Changed:", changed)
print()
print("New endpoints:")
print("  GET /api/live/health")
print("  GET /api/live/environment/{location}")
