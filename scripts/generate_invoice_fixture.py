from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

target = Path(__file__).parents[1] / "tests" / "fixtures" / "invoice.pdf"
target.parent.mkdir(parents=True, exist_ok=True)

canvas = Canvas(str(target), pagesize=A4)
canvas.setTitle("eZEUS Testrechnung")
canvas.setFont("Helvetica-Bold", 18)
canvas.drawString(72, 770, "RECHNUNG")
canvas.setFont("Helvetica", 13)
canvas.drawString(72, 720, "Rechnungsnummer: R-4711")
canvas.drawString(72, 690, "Rechnungsdatum: 24.07.2026")
canvas.drawString(72, 620, "Leistung Dokumentenverarbeitung")
canvas.drawString(72, 560, "Gesamtbetrag: 1.234,56 EUR")
canvas.save()

print(f"generated={target} bytes={target.stat().st_size}")
