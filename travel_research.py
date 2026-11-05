"""Small, source-aware research stage for Version B planning."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import os
import re

import requests


def _search(query: str, limit: int = 5) -> list[dict[str, str]]:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return []
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"query": query, "search_depth": "basic", "max_results": limit,
                  "include_answer": False, "include_images": False},
            timeout=15,
        )
        response.raise_for_status()
        return [{"title": item.get("title", "")[:140], "url": item.get("url", "")[:500],
                 "content": item.get("content", "")[:650]}
                for item in response.json().get("results", []) if item.get("url", "").startswith("https://")]
    except (requests.RequestException, ValueError):
        return []


def research_destination(destination: str, budget: int, days: int) -> dict:
    nightly_target = max(1200, round(budget * .35 / max(days - 1, 1)))
    queries = {
        "attractions": f"{destination} India best real attractions neighborhoods practical travel route official tourism",
        "restaurants": f"{destination} India named restaurants local cuisine where to eat guide",
        "hotels": f"{destination} India hotels accommodation around INR {nightly_target} per night named properties",
    }
    with ThreadPoolExecutor(max_workers=3) as pool:
        values = list(pool.map(_search, queries.values()))
    return dict(zip(queries, values)) | {"researched_on": date.today().isoformat()}


def observed_hotel_rate(name: str, destination: str) -> dict:
    """Return an indexed INR rate only when a result names the same property."""
    results = _search(f'"{name}" {destination} hotel room price INR per night', 5)
    words = [word for word in re.findall(r"[a-z0-9]+", name.lower()) if len(word) > 2]
    for item in results:
        title = item["title"].lower()
        if not words or sum(word in title for word in words) < max(1, len(words) - 1):
            continue
        content = item["content"].lower()
        pattern = r"(?:₹|INR\s*|Rs\.?\s*)([\d,]{3,8}).{0,35}(?:per\s*night|/night|1\s*night)"
        for match in re.finditer(pattern, content, flags=re.I | re.S):
            context = content[max(0, match.start() - 90):match.end() + 35]
            if any(term in context for term in ("extra bed", "crib", "per person", "children", "taxes & fees", "taxes and fees")):
                continue
            raw = match.group(1)
            value = int(raw.replace(",", ""))
            if 800 <= value <= 100000:
                return {"nightly_price_inr": value, "price_source_url": item["url"],
                        "price_checked_on": date.today().isoformat()}
    return {}


def named_place_supported(name: str, known_text: str) -> bool:
    """Require a substantial exact name match in retrieved material."""
    words = [word for word in re.findall(r"[a-z0-9]+", name.lower()) if len(word) > 2]
    haystack = " ".join(word for word in re.findall(r"[a-z0-9]+", known_text.lower()) if len(word) > 2)
    phrase = " ".join(words)
    return bool(phrase and phrase in haystack)
