
from pathlib import Path
main = Path(__file__).resolve().parent / "main.py"
text = main.read_text(encoding="utf-8")
imp = "from backend.report_service import router as report_router"
inc = "app.include_router(report_router)"
if imp not in text:
    text = imp + "\n" + text
if inc not in text:
    text = text.rstrip() + "\n" + inc + "\n"
main.write_text(text, encoding="utf-8")
print("REPORT FEATURE INSTALLED")
print("Endpoints: /api/reports/{location} and /api/reports/{location}/pdf")
