
from pathlib import Path

main_file = Path(__file__).resolve().parent / "main.py"
text = main_file.read_text(encoding="utf-8")

import_line = "from backend.traffic_exposure import router as traffic_exposure_router"
include_line = "app.include_router(traffic_exposure_router)"

changed = False

if import_line not in text:
    text = import_line + "\n" + text
    changed = True

if include_line not in text:
    text = text.rstrip() + "\n" + include_line + "\n"
    changed = True

main_file.write_text(text, encoding="utf-8")

print("Traffic feature installation complete.")
print("main.py updated." if changed else "Traffic feature was already installed.")
print("New endpoints:")
print("  /api/traffic/health")
print("  /api/traffic/exposure/{location}")
print("  /api/traffic/all")
