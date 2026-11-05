"""Photo-rich PDF for structured Version B itineraries."""

from html import escape
from io import BytesIO
from pathlib import Path
import re
from urllib.parse import urlparse
from uuid import uuid4

import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer
from PIL import Image as PILImage

from version_b_service import TripPlan
from place_enrichment import HEADERS


def _pdf_text(value: str) -> str:
    replacements = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                                  "–": "-", "—": "-", "‑": "-", "…": "..."})
    return escape(value.translate(replacements))


def _photo(url: str):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"upload.wikimedia.org", "thumb.wikimedia.org"}:
        return None
    try:
        response = requests.get(url, headers=HEADERS, timeout=8, stream=True)
        response.raise_for_status()
        content = response.raw.read(2_000_001)
        if len(content) > 2_000_000:
            return None
        stream = BytesIO(content)
        with PILImage.open(stream) as picture:
            width, height = picture.size
            if width < 200 or height < 150:
                return None
        stream.seek(0)
        display_width = 10.5 * cm
        return Image(stream, width=display_width, height=min(display_width * height / width, 4.8 * cm))
    except (requests.RequestException, OSError, ValueError):
        return None


def save_v2_pdf(destination: str, plan: TripPlan, directory: str) -> str:
    output = Path(directory)
    output.mkdir(parents=True, exist_ok=True)
    filename = f"Voyage_{uuid4().hex}.pdf"
    path = output / filename
    styles = getSampleStyleSheet()
    title = ParagraphStyle("VoyageTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=24, leading=30, textColor=colors.HexColor("#193c49"), spaceAfter=15)
    day_style = ParagraphStyle("VoyageDay", parent=styles["Heading1"], fontSize=17, leading=22, textColor=colors.HexColor("#193c49"), spaceBefore=15, spaceAfter=7)
    activity_style = ParagraphStyle("VoyageActivity", parent=styles["Heading2"], fontSize=11, leading=15, textColor=colors.HexColor("#245a68"), spaceBefore=12, spaceAfter=4, keepWithNext=True)
    body = ParagraphStyle("VoyageBody", parent=styles["BodyText"], fontSize=9.5, leading=14, spaceAfter=5)
    credit = ParagraphStyle("VoyageCredit", parent=body, fontSize=7.5, leading=10, textColor=colors.HexColor("#66777a"))
    story = [Paragraph(_pdf_text(f"{destination} | Your Voyage itinerary"), title),
             Paragraph(_pdf_text(plan.overview), body),
             Paragraph(f"Estimated local spend from INR {plan.estimated_total_inr:,}. Prices and travel details are estimates.", body),
             Paragraph(_pdf_text(plan.estimate_basis), credit) if plan.estimate_basis else Spacer(1, 1),
             Spacer(1, 10)]
    if plan.hotels:
        story.append(Paragraph("Where to stay", day_style))
        for hotel in plan.hotels:
            detail = f"{hotel.area} | {hotel.why_stay}".strip(" |")
            if hotel.nightly_price_inr:
                detail += f" | Indexed listing: INR {hotel.nightly_price_inr:,} per night, checked {hotel.price_checked_on}; confirm for your dates."
            else:
                detail += " | Check the current rate for your dates."
            source = hotel.price_source_url or hotel.source_url
            link = f' <link href="{escape(source, quote=True)}">Source</link>' if source.startswith("https://") else ""
            story.append(Paragraph(f"<b>{_pdf_text(hotel.name)}</b> | {_pdf_text(detail)}{link}", body))
            story.append(Spacer(1, 3))
    if plan.restaurants:
        story.append(Paragraph("Where to eat", day_style))
        for restaurant in plan.restaurants:
            link = f' <link href="{escape(restaurant.source_url, quote=True)}">Source</link>' if restaurant.source_url.startswith("https://") else ""
            story.append(Paragraph(f"<b>{_pdf_text(restaurant.name)}</b> | {_pdf_text(restaurant.area)}: {_pdf_text(restaurant.what_to_try)}{link}", body))
            story.append(Spacer(1, 2))
    for number, day in enumerate(plan.days, 1):
        clean_title = re.sub(r"^Day\s*\d+\s*[:–—-]?\s*", "", day.title, flags=re.I).strip()
        if not clean_title:
            clean_title = day.activities[0].title
        story.extend([Paragraph(_pdf_text(f"Day {number}: {clean_title}"), day_style), Paragraph(_pdf_text(day.intro), body)])
        for activity in day.activities:
            section = [Paragraph(_pdf_text(f"{activity.time} | {activity.title}"), activity_style)]
            photo = _photo(activity.image_url) if activity.image_url else None
            if photo:
                source = escape(activity.image_page_url, quote=True)
                caption = _pdf_text(f"Photo: {activity.image_credit}") + f' | <link href="{source}">Source and license</link>'
                section.append(KeepTogether([photo, Spacer(1, 4), Paragraph(caption, credit)]))
            section.append(Paragraph(_pdf_text(activity.description), body))
            if activity.why_famous:
                section.append(Paragraph("<b>Why it matters:</b> " + _pdf_text(activity.why_famous), body))
            if activity.duration:
                section.append(Paragraph("<b>Time to allow:</b> " + _pdf_text(activity.duration), body))
            if activity.getting_there:
                section.append(Paragraph("<b>Getting there:</b> " + _pdf_text(activity.getting_there), body))
            if activity.practical_tip:
                section.append(Paragraph("<b>Tip:</b> " + _pdf_text(activity.practical_tip), body))
            if activity.estimated_cost_inr is not None:
                section.append(Paragraph(f"Estimated activity cost: INR {activity.estimated_cost_inr:,}", credit))
            story.extend(section)
    if plan.practical_notes:
        story.append(Paragraph("Before you go", day_style))
        for note in plan.practical_notes:
            story.append(Paragraph("&bull; " + _pdf_text(note), body))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Check opening times, routes, prices and weather before booking. Photo credits and license details are linked on the Wikimedia file pages shown above.", credit))
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=1.8*cm, bottomMargin=1.8*cm).build(story)
    return filename
