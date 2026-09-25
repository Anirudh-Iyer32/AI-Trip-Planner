"""
itinerary_structurer.py
Normalizes, parses, and validates raw AI travel agent output into a structured, reliable JSON schema
for web UI cards/tables and ReportLab PDF components.

Handles unicode characters, emoji headers, day-by-day markdown lists, and free-form sections.
"""

import re
import unicodedata
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ActivityItem(BaseModel):
    time: str = ""
    title: str = ""
    category: str = "activity"  # transport | hotel | attraction | food | activity | free_time
    description: str = ""
    location: Optional[str] = None
    estimated_cost: Optional[str] = None
    duration: Optional[str] = None
    notes: Optional[str] = None


class DayPlan(BaseModel):
    day_number: int
    title: str = ""
    theme: Optional[str] = None
    activities: List[ActivityItem] = Field(default_factory=list)
    meals: Optional[Dict[str, str]] = None
    day_notes: Optional[str] = None


class TransportOption(BaseModel):
    mode: str = ""
    route: str = ""
    provider_or_details: str = ""
    estimated_cost: Optional[str] = None
    duration: Optional[str] = None
    notes: Optional[str] = None
    is_live_data: bool = False


class AccommodationOption(BaseModel):
    name: str = ""
    hotel_type: str = ""
    location: str = ""
    price_per_night: Optional[str] = None
    rating_or_amenities: Optional[str] = None
    booking_notes: Optional[str] = None


class DiningRecommendation(BaseModel):
    name: str = ""
    cuisine: str = ""
    must_try: Optional[str] = None
    price_range: Optional[str] = None
    area: Optional[str] = None


class BudgetCategory(BaseModel):
    category: str
    amount: str
    percentage: Optional[str] = None
    notes: Optional[str] = None


class StructuredItinerary(BaseModel):
    destination: str = ""
    origin: Optional[str] = None
    duration_days: int = 4
    party_size: Optional[str] = "2 Travelers"
    currency: str = "INR"
    total_budget: Optional[str] = None
    travel_style: Optional[str] = None
    trip_dates: Optional[str] = None
    summary: str = ""
    weather_summary: Optional[str] = None

    transportation: List[TransportOption] = Field(default_factory=list)
    accommodation: List[AccommodationOption] = Field(default_factory=list)
    dining: List[DiningRecommendation] = Field(default_factory=list)
    budget_breakdown: List[BudgetCategory] = Field(default_factory=list)
    days: List[DayPlan] = Field(default_factory=list)

    tips_and_guidelines: List[str] = Field(default_factory=list)
    data_classification: Dict[str, str] = Field(default_factory=lambda: {
        "weather": "live_api",
        "rates": "live_api",
        "pricing": "estimated",
        "inventory": "estimated_reference"
    })
    raw_markdown: Optional[str] = None


def normalize_text(text: str) -> str:
    """Normalizes non-breaking spaces, unicode hyphens, and emoji variations."""
    if not text:
        return ""
    text = unicodedata.normalize('NFKD', text)
    text = text.replace('\u202f', ' ').replace('\u00a0', ' ').replace('\u2009', ' ')
    text = text.replace('\u2011', '-').replace('\u2012', '-').replace('\u2013', '-').replace('\u2014', '-')
    return text


def parse_table(table_text: str) -> List[Dict[str, str]]:
    """Helper to parse a pipe-delimited markdown table into a list of row dicts."""
    lines = [l.strip() for l in table_text.strip().splitlines() if '|' in l]
    if len(lines) < 3:
        return []
    headers = [h.strip().strip('*_') for h in lines[0].split('|')[1:-1]]
    rows = []
    for line in lines[2:]:
        cols = [c.strip() for c in line.split('|')[1:-1]]
        if not any(cols):
            continue
        if len(cols) < len(headers):
            cols += [''] * (len(headers) - len(cols))
        rows.append(dict(zip(headers, cols[:len(headers)])))
    return rows


def extract_category_from_text(title: str, desc: str) -> str:
    combined = (title + " " + desc).lower()
    if any(k in combined for k in ["flight", "train", "cab", "drive", "airport", "station",
                                    "arrival", "departure", "transfer", "auto", "bus", "metro"]):
        return "transport"
    if any(k in combined for k in ["hotel", "check-in", "check in", "resort", "stay",
                                    "checkout", "check out", "overnight", "accommodation"]):
        return "hotel"
    if any(k in combined for k in ["breakfast", "lunch", "dinner", "cafe", "restaurant",
                                    "street food", "snack", "dine", "meal", "thali", "kachori",
                                    "lassi", "chai"]):
        return "food"
    if any(k in combined for k in ["palace", "fort", "temple", "museum", "monument", "mahal",
                                    "ghat", "lake", "viewpoint", "bazaar", "market",
                                    "jantar mantar", "amber", "hawa", "city palace"]):
        return "attraction"
    if any(k in combined for k in ["leisure", "free time", "relax", "spa", "pool", "stroll",
                                    "pack", "shopping"]):
        return "free_time"
    return "activity"


def parse_day_activities(day_content: str) -> List[ActivityItem]:
    """
    Parse activity lines from a day's markdown content.
    Strategy 1: bullet items with a time/slot prefix (e.g. - **09:00 AM:** text)
    Strategy 2: any non-trivial bullet item
    """
    activities = []

    # Strategy 1: time-prefixed bullets
    time_pattern = re.compile(
        r'^\s*[-*]\s*'
        r'(?:\*\*)?'
        r'(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?'
        r'|Morning|Afternoon|Midday|Noon|Evening|Night|Overnight)'
        r'(?:\*\*)?'
        r'\s*[:\-\u2014\u2013]\s*'
        r'(.+)',
        re.IGNORECASE | re.MULTILINE
    )
    found = time_pattern.findall(day_content)

    if found:
        for slot_time, slot_desc in found:
            slot_clean = slot_desc.strip().rstrip('*').strip()
            title_part = slot_clean.split('.')[0].split('(')[0].strip().strip('*').strip()
            cost_match = re.search(r'(?:[\u20b9\$\u20ac]|INR)\s*[\d,]+(?:\s*/\s*person)?',
                                   slot_clean)
            activities.append(ActivityItem(
                time=slot_time.strip(),
                title=title_part if title_part else slot_time.strip(),
                category=extract_category_from_text(title_part, slot_clean),
                description=slot_clean,
                estimated_cost=cost_match.group(0) if cost_match else None
            ))
    else:
        # Strategy 2: plain bullet items
        for line in day_content.splitlines():
            clean = line.strip()
            if not clean.startswith(('-', '*', '\u2022')):
                continue
            clean_l = clean.lstrip('-*\u2022 \t').strip()
            if len(clean_l) < 10 or clean_l.startswith('#') or clean_l.startswith('|'):
                continue
            cost_match = re.search(r'(?:[\u20b9\$\u20ac]|INR)\s*[\d,]+', clean_l)
            title = clean_l.split('.')[0].strip('*').strip()[:80]
            activities.append(ActivityItem(
                time="Flexible",
                title=title,
                category=extract_category_from_text(title, clean_l),
                description=clean_l,
                estimated_cost=cost_match.group(0) if cost_match else None
            ))

    return activities


def _clean_table_cell(value: str) -> str:
    """Turn a Markdown/HTML table cell into plain text without losing its content."""
    value = re.sub(r'<br\s*/?>', '\n', value, flags=re.IGNORECASE)
    value = re.sub(r'<[^>]+>', '', value)
    return value.replace('\\n', '\n').strip()


def _table_cell_activities(value: str, time: str = "Flexible") -> List[ActivityItem]:
    """Build one activity per line (or <br>) in an itinerary-table cell."""
    activities = []
    for item in _clean_table_cell(value).splitlines():
        item = re.sub(r'^\s*(?:[-*•]+|\d+[.)])\s*', '', item).strip()
        item = re.sub(r'\s+', ' ', item).strip()
        if not item or item in {'-', '—', '–'}:
            continue
        # A table cell can contain an explicit empty overnight placeholder.
        if re.match(r'^overnight\s*:\s*[-—–]\s*$', item, re.IGNORECASE):
            continue
        title = re.sub(r'[*_`]', '', item).split('.')[0].split('(')[0].strip()
        cost_match = re.search(r'(?:[₹$€]|INR|USD|EUR)\s*[\d,]+(?:\s*/\s*(?:person|pp|night))?', item,
                               re.IGNORECASE)
        activities.append(ActivityItem(
            time=time,
            title=title or item,
            category=extract_category_from_text(title, item),
            description=item,
            estimated_cost=cost_match.group(0) if cost_match else None
        ))
    return activities


def segment_itinerary_sections(raw_text: str) -> List[Dict[str, str]]:
    """Return named Markdown sections whose headings identify itinerary alternatives.

    The heading text is intentionally matched loosely because agent output may include
    numbering, emoji, or different plan names (for example, Classic or Off-Beat).
    """
    heading_re = re.compile(
        r'^(?P<hashes>#{2,6})\s+(?P<title>[^\n]*\bitinerar(?:y|ies)\b[^\n]*)\s*$',
        re.IGNORECASE | re.MULTILINE,
    )
    headings = list(heading_re.finditer(raw_text))
    if len(headings) < 2:
        return []

    sections = []
    used_ids = set()
    for index, heading in enumerate(headings):
        raw_heading = heading.group("title").strip()
        name = re.sub(r'^\s*\d+\s*[^\w\s]*\s*', '', raw_heading).strip()
        name = name or raw_heading
        normalized_name = normalize_text(name).lower()
        if re.search(r'off\W*beat', normalized_name):
            alternative_id, kind = "off-beat", "off_beat"
        elif re.search(r'classic|tourist', normalized_name):
            alternative_id, kind = "classic", "classic"
        else:
            slug_source = re.sub(r'\bitinerary\b', '', normalized_name).strip()
            alternative_id = re.sub(r'[^a-z0-9]+', '-', slug_source).strip('-') or f"alternative-{index + 1}"
            kind = alternative_id.replace('-', '_')

        base_id = alternative_id
        duplicate = 2
        while alternative_id in used_ids:
            alternative_id = f"{base_id}-{duplicate}"
            duplicate += 1
        used_ids.add(alternative_id)

        # An alternative ends at the next heading at its level or above. This
        # excludes shared post-plan comparison sections from the final alternative.
        heading_level = len(heading.group("hashes"))
        next_section_re = re.compile(rf'^#{{1,{heading_level}}}\s+', re.MULTILINE)
        next_section = next_section_re.search(raw_text, heading.end())
        section_end = next_section.start() if next_section else len(raw_text)
        sections.append({
            "id": alternative_id,
            "name": name,
            "kind": kind,
            "raw_markdown": raw_text[heading.start():section_end].strip(),
        })
    return sections


def parse_markdown_to_structured(raw_text: str, query_text: str = "") -> StructuredItinerary:
    """
    Main parser: transforms raw agent markdown into a clean StructuredItinerary.
    """
    text = normalize_text(raw_text)
    itinerary = StructuredItinerary(raw_markdown=raw_text)

    # 1. Infer trip metadata from the query string
    if query_text:
        q = normalize_text(query_text)
        m = re.search(r'\bto\s+([A-Za-z\s]+?)(?:\s+for|\s+from|\s+with|\s+in|\.|$)', q, re.IGNORECASE)
        if m:
            itinerary.destination = m.group(1).strip().title()
        m = re.search(r'\bfrom\s+([A-Za-z\s]+?)(?:\s+to|\s+with|\s+for|\.|$)', q, re.IGNORECASE)
        if m:
            itinerary.origin = m.group(1).strip().title()
        m = re.search(r'(\d+)[-\s]*(?:day|days)', q, re.IGNORECASE)
        if m:
            itinerary.duration_days = int(m.group(1))
        m = re.search(r'(\d+)\s*(?:people|person|travelers|adults|pax)', q, re.IGNORECASE)
        if m:
            itinerary.party_size = f"{m.group(1)} Travelers"
        elif "couple" in q.lower() or "for 2" in q.lower():
            itinerary.party_size = "2 Travelers"
        m = re.search(
            r'(?:[\u20b9\$\u20ac]|INR|USD|EUR)\s*([\d,]+(?:k|lakh|lac)?)'
            r'|\b([\d,]+)\s*(?:INR|rupees|USD|EUR)',
            q, re.IGNORECASE
        )
        if m:
            b_val = m.group(1) or m.group(2)
            if '\u20b9' in q or 'INR' in q.upper() or 'rupee' in q.lower():
                itinerary.currency = "INR"
                itinerary.total_budget = f"\u20b9{b_val}"
            else:
                itinerary.currency = "USD"
                itinerary.total_budget = f"${b_val}"

    # 2. Fallback: extract destination from body text
    if not itinerary.destination:
        m = re.search(
            r'(?:trip\s+to|itinerary\s+for|destination[:\s]+)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            text
        )
        if m:
            itinerary.destination = m.group(1).strip()

    # 3. Try to get a summary from the intro paragraph
    intro_m = re.match(r'^([^\n#]{40,500})', text.strip())
    if intro_m:
        intro = intro_m.group(1).strip()
        if not intro.startswith('|'):
            itinerary.summary = intro[:300]

    # 4. Parse top-level ## sections for transport, accommodation, food, budget, weather
    section_pattern = re.compile(r'^#{1,2}\s+(.+)$', re.MULTILINE)
    sec_positions = [(m.start(), m.group(1).strip()) for m in section_pattern.finditer(text)]
    sec_positions.append((len(text), '__END__'))

    for i, (pos, sec_title) in enumerate(sec_positions[:-1]):
        next_pos = sec_positions[i + 1][0]
        sec_content = text[pos:next_pos]
        sl = sec_title.lower()

        body_start = sec_content.find('\n')
        sec_body = sec_content[body_start:].strip() if body_start != -1 else sec_content

        table_m = re.search(
            r'(\|(?:[^\n]+\|)+\n\|(?:[-:| ]+\|)+\n(?:\|(?:[^\n]+\|)+\n?)+)',
            sec_body
        )
        ptable = parse_table(table_m.group(1)) if table_m else []

        # Summary / overview
        if any(k in sl for k in ["summary", "overview", "quick look", "at a glance"]):
            if not itinerary.summary:
                note_lines = [l.strip('> -*') for l in sec_body.splitlines()
                              if l.strip() and not l.startswith('|') and len(l.strip()) > 20]
                if note_lines:
                    itinerary.summary = note_lines[0]

        # Weather (not a replan section, not a day section)
        elif "weather" in sl and "replan" not in sl and "day" not in sl:
            if ptable:
                summaries = []
                for r in ptable:
                    d = r.get("Date") or r.get("Day") or ""
                    cond = r.get("Conditions") or r.get("Weather") or r.get("Condition") or ""
                    tmax = r.get("Max") or r.get("High") or r.get("Temp") or ""
                    tmin = r.get("Min") or r.get("Low") or ""
                    t_str = f"{tmax}C" if tmax else ""
                    if tmin:
                        t_str += f"/{tmin}C"
                    part = f"{d}: {cond} ({t_str})".strip(": ()")
                    if part:
                        summaries.append(part)
                if summaries:
                    itinerary.weather_summary = " | ".join(summaries[:4])
            else:
                lines = [l.strip("-* \t") for l in sec_body.splitlines()
                         if l.strip() and not l.startswith('|') and not l.startswith('#')]
                if lines:
                    itinerary.weather_summary = " | ".join(lines[:3])

        # Accommodation
        elif (any(k in sl for k in ["accommodation", "hotel", "stay", "lodging"])
              and "day" not in sl and not itinerary.accommodation):
            for r in ptable:
                name = loc = price = high = hotel_type = ""
                for k, v in r.items():
                    kl = k.lower()
                    if any(x in kl for x in ["hotel", "name", "property", "resort"]):
                        name = v.strip("* ")
                    elif any(x in kl for x in ["rate", "price", "cost", "night"]):
                        price = v.strip("* ")
                    elif any(x in kl for x in ["location", "area", "zone"]):
                        loc = v.strip()
                    elif any(x in kl for x in ["highlight", "amenit", "feature", "rating"]):
                        high = v.strip()
                    elif any(x in kl for x in ["type", "category", "tier"]):
                        hotel_type = v.strip()
                if name:
                    itinerary.accommodation.append(AccommodationOption(
                        name=name, location=loc, price_per_night=price,
                        rating_or_amenities=high, hotel_type=hotel_type
                    ))

        # Transportation
        elif (any(k in sl for k in ["transport", "flight", "transit", "getting"])
              and "day" not in sl and not itinerary.transportation):
            for r in ptable:
                mode = cost = details = route = duration = ""
                for k, v in r.items():
                    kl = k.lower()
                    if any(x in kl for x in ["mode", "option", "type", "vehicle"]):
                        mode = v.strip("* ")
                    elif any(x in kl for x in ["cost", "price", "fare"]):
                        cost = v.strip("* ")
                    elif any(x in kl for x in ["detail", "note", "how to", "via", "operator"]):
                        details = v.strip()
                    elif any(x in kl for x in ["route", "from", "journey", "connection"]):
                        route = v.strip()
                    elif any(x in kl for x in ["duration", "time", "hours"]):
                        duration = v.strip()
                if mode:
                    itinerary.transportation.append(TransportOption(
                        mode=mode, route=route or details[:60],
                        provider_or_details=details, estimated_cost=cost,
                        duration=duration, is_live_data=True
                    ))

        # Food / Dining
        elif (any(k in sl for k in ["food", "dining", "restaurant", "culinary", "eat"])
              and "day" not in sl and not itinerary.dining):
            for r in ptable:
                name = cuisine = cost = dish = area = ""
                for k, v in r.items():
                    kl = k.lower()
                    if any(x in kl for x in ["restaurant", "place", "spot", "name", "venue"]):
                        name = v.strip("* ")
                    elif any(x in kl for x in ["cuisine", "style", "type"]):
                        cuisine = v.strip()
                    elif any(x in kl for x in ["cost", "price", "range"]):
                        cost = v.strip()
                    elif any(x in kl for x in ["must", "special", "dish", "try"]):
                        dish = v.strip()
                    elif any(x in kl for x in ["area", "location", "zone"]):
                        area = v.strip()
                if name:
                    itinerary.dining.append(DiningRecommendation(
                        name=name, cuisine=cuisine, price_range=cost,
                        must_try=dish, area=area
                    ))

        # Budget Breakdown
        elif (any(k in sl for k in ["budget", "cost breakdown", "expense", "financial"])
              and "day" not in sl and not itinerary.budget_breakdown):
            for r in ptable:
                cat = amt = notes = ""
                for k, v in r.items():
                    kl = k.lower()
                    if any(x in kl for x in ["category", "item", "expense", "component"]):
                        cat = v.strip("* ")
                    elif any(x in kl for x in ["cost", "amount", "price", "total"]):
                        amt = v.strip("* ")
                    elif any(x in kl for x in ["note", "detail", "remark"]):
                        notes = v.strip()
                if cat and not cat.lower().startswith("total"):
                    itinerary.budget_breakdown.append(BudgetCategory(
                        category=cat, amount=amt, notes=notes
                    ))

        # Tips / Guidelines
        elif any(k in sl for k in ["tip", "guideline", "advice", "important"]):
            for line in sec_body.splitlines():
                clean = line.strip().lstrip('-*\u2022 \t')
                if len(clean) > 15:
                    itinerary.tips_and_guidelines.append(clean)

    # 5. Day-by-Day Parsing — PRIMARY APPROACH
    # Find ALL ### Day N / ## Day N headers then slice content between them.
    # This runs INDEPENDENTLY of the section loop to avoid any guard-clause issues.
    day_header_re = re.compile(
        r'^#{2,3}\s*Day\s*(\d+)\s*[:\-\u2014\u2013]?\s*([^\n]*)',
        re.MULTILINE | re.IGNORECASE
    )
    day_headers = list(day_header_re.finditer(text))

    if day_headers:
        for idx, mh in enumerate(day_headers):
            day_num = int(mh.group(1))
            suffix = mh.group(2).strip().strip('*').strip()
            day_title = f"Day {day_num}: {suffix}" if suffix else f"Day {day_num}"

            content_start = mh.end()
            content_end = day_headers[idx + 1].start() if idx + 1 < len(day_headers) else len(text)
            day_content = text[content_start:content_end]

            activities = parse_day_activities(day_content)
            itinerary.days.append(DayPlan(
                day_number=day_num,
                title=day_title,
                activities=activities
            ))

    # 6. Fallback: table-format single-table day itinerary
    if not itinerary.days:
        table_m = re.search(
            r'(\|(?:[^\n]+\|)+\n\|(?:[-:| ]+\|)+\n(?:\|(?:[^\n]+\|)+\n?)+)',
            text
        )
        if table_m:
            rows = parse_table(table_m.group(1))
            for idx, r in enumerate(rows, start=1):
                day_raw = main_activities = meals = transport = extras = hotel_stay = ""
                morning = midday = evening = ""
                for k, v in r.items():
                    kl = k.lower()
                    if kl in ("day",) or (kl.startswith("day") and len(kl) < 8):
                        day_raw = v.strip("* ")
                    elif any(x in kl for x in ["main activit", "activities", "itinerary", "plan"]):
                        main_activities = v.strip()
                    elif "morning" in kl:
                        morning = v.strip()
                    elif any(x in kl for x in ["mid", "afternoon", "lunch"]):
                        midday = v.strip()
                    elif any(x in kl for x in ["evening", "night", "dinner"]):
                        evening = v.strip()
                    elif any(x in kl for x in ["meal", "restaurant", "dining", "food"]):
                        meals = v.strip()
                    elif any(x in kl for x in ["transport", "travel", "transfer"]):
                        transport = v.strip()
                    elif any(x in kl for x in ["entry", "fee", "extra", "ticket"]):
                        extras = v.strip()
                    elif any(x in kl for x in ["accom", "hotel", "stay"]):
                        hotel_stay = v.strip()
                day_num = idx
                nm = re.search(r'(\d+)', day_raw)
                if nm:
                    day_num = int(nm.group(1))
                title_suffix = re.sub(r'^\s*\d+\s*[^\w\s]\s*', '', day_raw).strip()
                d_title = f"Day {day_num}: {title_suffix}" if title_suffix else f"Day {day_num}"

                # The generated itinerary uses one rich `Main Activities` column,
                # with items separated by <br>.  Preserve every item rather than
                # treating the whole cell as one activity.
                activities = _table_cell_activities(main_activities)
                if not activities:
                    for slot_time, slot_val in [("Morning", morning), ("Afternoon", midday),
                                                 ("Evening", evening)]:
                        activities.extend(_table_cell_activities(slot_val, slot_time))

                # Surface the other daily columns in the timeline too, so their
                # hotel, meal, transport, and entry-fee details are not discarded.
                for label, value, category in [
                    ("Meals", meals, "food"),
                    ("Transport", transport, "transport"),
                    ("Entry fees & extras", extras, "attraction"),
                ]:
                    for activity in _table_cell_activities(value, label):
                        activity.category = category
                        activities.append(activity)
                hotel_details = _clean_table_cell(hotel_stay)
                if hotel_details and hotel_details not in {"-", "—", "–"}:
                    hotel_lines = [line.strip() for line in hotel_details.splitlines() if line.strip()]
                    hotel_name = re.sub(r'[*_`]', '', hotel_lines[0]).strip()
                    hotel_cost = re.search(r'(?:[₹$€]|INR|USD|EUR)\s*[\d,]+(?:\s*/\s*(?:person|pp|night))?',
                                           hotel_details, re.IGNORECASE)
                    activities.append(ActivityItem(
                        time="Overnight",
                        title=f"Stay at {hotel_name}",
                        category="hotel",
                        description=hotel_details,
                        estimated_cost=hotel_cost.group(0) if hotel_cost else None
                    ))
                itinerary.days.append(DayPlan(
                    day_number=day_num, title=d_title, activities=activities,
                    meals={"details": _clean_table_cell(meals)} if _clean_table_cell(meals) else None
                ))

    # 7. Finalize
    itinerary.days.sort(key=lambda d: d.day_number)
    if itinerary.days:
        itinerary.duration_days = max(itinerary.duration_days, len(itinerary.days))
    if not itinerary.summary:
        dest_label = itinerary.destination or "your destination"
        itinerary.summary = (
            f"Bespoke {itinerary.duration_days}-day travel itinerary for {dest_label} "
            f"curated for a balanced heritage and culinary journey."
        )
    return itinerary


def validate_itinerary_consistency(itinerary: StructuredItinerary) -> Dict[str, Any]:
    issues = []
    if itinerary.days and itinerary.duration_days != len(itinerary.days):
        issues.append(f"Adjusted duration from {itinerary.duration_days} to {len(itinerary.days)} days.")
        itinerary.duration_days = len(itinerary.days)
    primary_currency = itinerary.currency or "INR"
    curr_sym = "\u20b9" if primary_currency == "INR" else ("$" if primary_currency == "USD" else "\u20ac")
    for b in itinerary.budget_breakdown:
        if b.amount and not any(c in b.amount for c in ["\u20b9", "$", "\u20ac", "INR", "USD", "EUR"]):
            b.amount = f"{curr_sym}{b.amount}"
    return {
        "valid": True,
        "issues_addressed": issues,
        "structured_itinerary": itinerary.dict()
    }


def structure_and_validate_itinerary(raw_output: str, query_text: str = "") -> Dict[str, Any]:
    """Main entry point."""
    try:
        structured_obj = parse_markdown_to_structured(raw_output, query_text)
        validated = validate_itinerary_consistency(structured_obj)
        selected_itinerary = validated["structured_itinerary"]

        # Keep the existing top-level schema as the first itinerary so all current
        # consumers (PDF, saved trips, and the single-plan UI) continue unchanged.
        # Alternative plans are an additive field parsed from their own sections.
        sections = segment_itinerary_sections(raw_output)
        if sections:
            alternatives = []
            for section in sections:
                alternative_obj = parse_markdown_to_structured(section["raw_markdown"], query_text)
                alternative = validate_itinerary_consistency(alternative_obj)["structured_itinerary"]
                alternatives.append({
                    "id": section["id"],
                    "name": section["name"],
                    "kind": section["kind"],
                    "raw_markdown": section["raw_markdown"],
                    "itinerary": alternative,
                })
            selected_itinerary["selected_alternative_id"] = alternatives[0]["id"]
            selected_itinerary["alternatives"] = alternatives

        return selected_itinerary
    except Exception as e:
        print(f"[Itinerary Structurer Error]: {e}")
        import traceback
        traceback.print_exc()
        return {
            "destination": "",
            "duration_days": 4,
            "party_size": "2 Travelers",
            "currency": "INR",
            "summary": "AI Travel Itinerary",
            "days": [],
            "raw_markdown": raw_output,
            "transportation": [],
            "accommodation": [],
            "dining": [],
            "budget_breakdown": [],
            "data_classification": {"status": "fallback"}
        }
