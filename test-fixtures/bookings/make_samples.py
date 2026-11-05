"""Generate fictional booking confirmations for the VOYAGE classroom demo."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
SAMPLES = [
    ("01-flight-mumbai-goa.pdf", "Example Air", "FLIGHT CONFIRMATION", [
        ("Booking reference", "DEMO-FL-4821"), ("Passenger", "Aarav Mehta"),
        ("Departure", "Mumbai (BOM), 12 December 2026 at 09:00"),
        ("Arrival", "Goa (GOI), 12 December 2026 at 10:15"),
        ("Status", "Sample confirmation for testing only"),
    ]),
    ("02-hotel-conflicting-dates.pdf", "Harbor View Stay", "HOTEL CONFIRMATION", [
        ("Booking reference", "DEMO-HT-9134"), ("Guest", "Aarav Mehta"),
        ("Property", "Harbor View Stay, Goa"),
        ("Check-in", "10 December 2026 at 14:00"),
        ("Checkout", "11 December 2026 at 11:00"),
        ("Status", "Sample confirmation for testing only"),
    ]),
    ("03-hotel-matching-dates.pdf", "Palm Courtyard Inn", "HOTEL CONFIRMATION", [
        ("Booking reference", "DEMO-HT-7158"), ("Guest", "Aarav Mehta"),
        ("Property", "Palm Courtyard Inn, Goa"),
        ("Check-in", "12 December 2026 at 14:00"),
        ("Checkout", "15 December 2026 at 11:00"),
        ("Status", "Sample confirmation for testing only"),
    ]),
]
for filename, provider, title, fields in SAMPLES:
    target = ROOT / filename
    pdf = canvas.Canvas(str(target), pagesize=A4)
    width, height = A4
    pdf.setFillColor(colors.HexColor('#193c49'))
    pdf.rect(0, height - 145, width, 145, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont('Helvetica-Bold', 13)
    pdf.drawString(46, height - 49, 'VOYAGE TEST MATERIAL')
    pdf.setFont('Helvetica-Bold', 24)
    pdf.drawString(46, height - 91, title)
    pdf.setFont('Helvetica', 12)
    pdf.drawString(46, height - 118, provider)
    y = height - 194
    for label, value in fields:
        pdf.setFillColor(colors.HexColor('#526b73'))
        pdf.setFont('Helvetica-Bold', 10)
        pdf.drawString(46, y, label.upper())
        pdf.setFillColor(colors.HexColor('#16313d'))
        pdf.setFont('Helvetica', 13)
        pdf.drawString(46, y - 22, value)
        y -= 70
    pdf.setStrokeColor(colors.HexColor('#dce4e1'))
    pdf.line(46, 95, width - 46, 95)
    pdf.setFillColor(colors.HexColor('#566d74'))
    pdf.setFont('Helvetica', 9)
    pdf.drawString(46, 72, 'FICTIONAL SAMPLE - NOT A REAL RESERVATION OR TICKET')
    pdf.save()

image = Image.new('RGB', (1200, 820), '#f5f7f4')
draw = ImageDraw.Draw(image)
try:
    title_font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 52)
    body_font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 30)
except OSError:
    title_font = body_font = ImageFont.load_default()
draw.rectangle((0, 0, 1200, 170), fill='#193c49')
draw.text((60, 46), 'ACTIVITY CONFIRMATION', fill='white', font=title_font)
draw.text((60, 220), 'Old Goa Walking Tour', fill='#16313d', font=title_font)
for index, line in enumerate([
    'Operator: Sample City Walks',
    'Booking reference: DEMO-ACT-2056',
    'Guest: Aarav Mehta',
    'Meeting place: Old Goa, Goa',
    'Starts: 13 December 2026 at 08:30',
    'Ends: 13 December 2026 at 11:00',
    'FICTIONAL SAMPLE - NOT A REAL BOOKING',
]):
    draw.text((60, 325 + index * 62), line, fill='#16313d', font=body_font)
image.save(ROOT / '04-activity-confirmation.png')
print('Created 3 PDFs and 1 PNG in', ROOT)
