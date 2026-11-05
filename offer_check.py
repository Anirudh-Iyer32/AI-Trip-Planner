"""Evidence-led checks for a travel offer before payment."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from difflib import SequenceMatcher
import ipaddress
import os
import re
from urllib.parse import quote, urlparse

import requests
from pydantic import BaseModel, Field, field_validator

FTC_GUIDE = "https://consumer.ftc.gov/articles/avoid-scams-when-you-travel"


class OfferRequest(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    destination: str = Field(min_length=2, max_length=100)
    listing_url: str = Field(default="", max_length=700)
    advertised_price: str = Field(default="", max_length=80)
    contact: str = Field(default="", max_length=120)
    payment_method: str = Field(default="unknown", max_length=60)
    offer_notes: str = Field(default="", max_length=500)

    @field_validator("listing_url")
    @classmethod
    def public_url(cls, value: str) -> str:
        if not value:
            return ""
        parsed = urlparse(value)
        host = parsed.hostname or ""
        if parsed.scheme != "https" or not host or parsed.username or parsed.password or "." not in host:
            raise ValueError("Use a public HTTPS listing URL without sign-in details.")
        try:
            ipaddress.ip_address(host)
            raise ValueError("Use a public website name, not an IP address.")
        except ValueError as exc:
            if "not an IP address" in str(exc):
                raise
        if host.lower().endswith((".local", ".internal", ".localhost")):
            raise ValueError("Use a public listing website.")
        return value


def _domain(value: str) -> str:
    return (urlparse(value).hostname or "").lower().removeprefix("www.")


def _tavily_search(query: str) -> list[dict]:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return []
    try:
        response = requests.post("https://api.tavily.com/search", headers={"Authorization": f"Bearer {key}"}, json={"query": query, "search_depth": "basic", "max_results": 6, "include_answer": False}, timeout=16)
        response.raise_for_status()
        return [{"title": str(row.get("title", ""))[:140], "url": str(row.get("url", ""))[:700], "snippet": str(row.get("content", ""))[:400]} for row in response.json().get("results", []) if str(row.get("url", "")).startswith("https://")]
    except (requests.RequestException, ValueError):
        return []


def _tavily_extract(url: str) -> str:
    key = os.getenv("TAVILY_API_KEY")
    if not key or not url:
        return ""
    try:
        response = requests.post("https://api.tavily.com/extract", headers={"Authorization": f"Bearer {key}"}, json={"urls": [url], "extract_depth": "basic"}, timeout=17)
        response.raise_for_status()
        return str((response.json().get("results") or [{}])[0].get("raw_content") or "")[:7000]
    except (requests.RequestException, ValueError, IndexError, TypeError):
        return ""


def _maps_search(name: str, destination: str) -> list[dict]:
    key = os.getenv("SERPAPI_API_KEY")
    if not key:
        return []
    try:
        response = requests.get("https://serpapi.com/search.json", params={"engine": "google_maps", "type": "search", "q": f"{name} {destination}", "hl": "en", "api_key": key}, timeout=18)
        response.raise_for_status()
        data = response.json()
        rows = data.get("local_results", [])
        if data.get("place_results"):
            rows = [data["place_results"], *rows]
        return [{"title": str(row.get("title", ""))[:120], "address": str(row.get("address", ""))[:200], "phone": str(row.get("phone", ""))[:80], "website": str(row.get("website", ""))[:700], "rating": row.get("rating"), "reviews": row.get("reviews"), "data_id": str(row.get("data_id", ""))[:200]} for row in rows[:6]]
    except (requests.RequestException, ValueError):
        return []


def _similar(a: str, b: str) -> bool:
    normalize = lambda text: " ".join(re.findall(r"[a-z0-9]+", text.lower()))
    left, right = normalize(a), normalize(b)
    return bool(left and right and SequenceMatcher(None, left, right).ratio() >= .72)


def check_offer(offer: OfferRequest) -> dict:
    with ThreadPoolExecutor(max_workers=3) as pool:
        web_future = pool.submit(_tavily_search, f'"{offer.name}" {offer.destination} official website reviews complaints')
        maps_future = pool.submit(_maps_search, offer.name, offer.destination)
        extract_future = pool.submit(_tavily_extract, offer.listing_url)
        web, places, listing_text = web_future.result(), maps_future.result(), extract_future.result()
    evidence = []
    listing_domain = _domain(offer.listing_url)
    matched = next((place for place in places if _similar(offer.name, place["title"])), None)
    if matched:
        maps_link = "https://www.google.com/maps/search/?api=1&query=" + quote(f'{matched["title"]} {matched["address"]}')
        evidence.append({"status": "match", "title": "A similarly named place appears on Maps", "detail": f'{matched["title"]} · {matched["address"] or "Address not listed"}. A Maps listing alone does not verify this offer or seller.', "source_url": maps_link, "source_label": "Google Maps via SerpApi"})
        website_domain = _domain(matched.get("website", ""))
        if listing_domain and website_domain:
            if listing_domain == website_domain:
                evidence.append({"status": "match", "title": "Listing domain matches the place website", "detail": f"Both use {website_domain}. Confirm dates and payment terms on the site itself.", "source_url": matched["website"], "source_label": "Website shown on Maps"})
            else:
                evidence.append({"status": "review", "title": "Listing and place website use different domains", "detail": f"Your listing uses {listing_domain}; the website shown on Maps uses {website_domain}. Booking platforms can be legitimate, but verify the seller and payment path directly.", "source_url": matched["website"], "source_label": "Website shown on Maps"})
        if offer.contact and matched.get("phone"):
            digits = lambda value: re.sub(r"\D", "", value)[-10:]
            if len(digits(offer.contact)) >= 8 and digits(offer.contact) == digits(matched["phone"]):
                evidence.append({"status": "match", "title": "Phone number matches the Maps listing", "detail": "The supplied phone number matches the number shown for this place. Confirm who is requesting payment.", "source_url": maps_link, "source_label": "Google Maps via SerpApi"})
            elif len(digits(offer.contact)) >= 8:
                evidence.append({"status": "review", "title": "Phone numbers differ", "detail": "The number supplied with the offer differs from the Maps listing. Call the independently listed number before paying.", "source_url": maps_link, "source_label": "Google Maps via SerpApi"})
    else:
        evidence.append({"status": "unknown", "title": "No confident place match found", "detail": "We could not confidently match the name to a Maps listing. This does not prove the offer is false; confirm the address and operator independently.", "source_url": "", "source_label": ""})
    if offer.listing_url:
        evidence.append({"status": "match" if listing_text and offer.name.lower() in listing_text.lower() else "unknown", "title": "Listing page content" if listing_text else "Listing page could not be read", "detail": "The provided listing contains the entered name. This confirms only what the page says, not whether its claims are true." if listing_text and offer.name.lower() in listing_text.lower() else "Check the original page yourself for property details, cancellation policy and seller identity.", "source_url": offer.listing_url, "source_label": "Your listing"})
    payment = offer.payment_method.lower()
    if payment in ("bank transfer", "gift card", "cryptocurrency", "wire transfer", "payment app"):
        evidence.append({"status": "review", "title": "Payment method needs extra caution", "detail": "Independent consumer guidance warns about travel offers requiring transfers, payment apps, gift cards or cryptocurrency. Confirm the seller and payment terms before paying.", "source_url": FTC_GUIDE, "source_label": "FTC travel scam guidance"})
    if offer.advertised_price:
        evidence.append({"status": "unknown", "title": "Advertised price is not independently confirmed", "detail": f"The offer says {offer.advertised_price}. Price depends on dates, guests, taxes and inclusions; ask for the full payable amount in writing.", "source_url": offer.listing_url, "source_label": "Your listing" if offer.listing_url else ""})
    if re.search(r"\b(pay today|pay now|send money now|immediate payment|last chance|only today)\b", offer.offer_notes, flags=re.I):
        evidence.append({"status": "review", "title": "The seller may be pressing for quick payment", "detail": "Your notes describe a time-limited payment request. Verify the operator and written terms before deciding; pressure is a reason to slow down.", "source_url": FTC_GUIDE, "source_label": "FTC travel scam guidance"})
    if re.search(r"\b(no refund|non.refundable|no cancellation)\b", offer.offer_notes, flags=re.I):
        evidence.append({"status": "review", "title": "Refund or cancellation terms need review", "detail": "Your notes mention restrictive terms. Ask for the full written policy and check it before paying.", "source_url": FTC_GUIDE, "source_label": "FTC travel scam guidance"})
    if not offer.listing_url:
        evidence.append({"status": "unknown", "title": "No listing URL supplied", "detail": "Add the listing link to compare its domain with the website shown for the place.", "source_url": "", "source_label": ""})
    independent = [row for row in web if _domain(row["url"]) not in (listing_domain, "")][:4]
    return {"checked_on": date.today().isoformat(), "offer": offer.model_dump(), "evidence": evidence, "independent_sources": independent, "place": matched, "sources_used": {"maps": bool(places), "web": bool(web), "listing": bool(listing_text)}, "summary": "Review the evidence and contact the property or operator through an independently found channel before paying. This check cannot certify an offer as safe or fraudulent."}
