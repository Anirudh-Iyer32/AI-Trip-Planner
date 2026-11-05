"""Optional, attributed place context from Wikipedia and Wikimedia Commons."""

from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from html import unescape
import re
from urllib.parse import quote

import requests

from version_b_service import TripPlan

HEADERS = {"User-Agent": "VoyageTripPlanner/0.1 (academic project; https://github.com/Anirudh-Iyer32/AI-Trip-Planner)"}


def _plain(value: str) -> str:
    return re.sub(r"<[^>]*>", "", unescape(value or "")).strip()


def _commons_photo(name: str) -> dict:
    """Search Commons file names and require the requested place words."""
    response = requests.get(
        "https://commons.wikimedia.org/w/api.php",
        params={"action": "query", "format": "json", "formatversion": 2,
                "generator": "search", "gsrsearch": f'intitle:"{name}"',
                "gsrnamespace": 6, "gsrlimit": 5, "prop": "imageinfo",
                "iiprop": "url|extmetadata", "iiurlwidth": 900,
                "iiextmetadatafilter": "Artist|LicenseShortName"},
        headers=HEADERS, timeout=8,
    )
    response.raise_for_status()
    words = {word for word in re.findall(r"[a-z0-9]+", name.lower()) if len(word) > 2}
    for page in response.json().get("query", {}).get("pages", []):
        title = page.get("title", "")
        file_words = set(re.findall(r"[a-z0-9]+", title.lower()))
        if not words or len(words & file_words) < max(1, len(words) - 1):
            continue
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        artist = _plain(meta.get("Artist", {}).get("value", ""))
        license_name = _plain(meta.get("LicenseShortName", {}).get("value", ""))
        thumb = info.get("thumburl", "")
        if artist and license_name and thumb.startswith(("https://upload.wikimedia.org/", "https://thumb.wikimedia.org/")):
            return {"image_url": thumb, "image_credit": f"{artist[:120]} · {license_name[:60]}",
                    "image_page_url": "https://commons.wikimedia.org/wiki/" + quote(title.replace(" ", "_"))}
    return {}


@lru_cache(maxsize=256)
def place_context(name: str) -> dict:
    name = name.strip()
    if len(name) < 4 or len(name) > 100:
        return {}
    try:
        response = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "format": "json", "formatversion": 2,
                    "titles": name, "redirects": 1, "prop": "pageimages|extracts",
                    "piprop": "thumbnail|name", "pithumbsize": 900,
                    "exintro": 1, "explaintext": 1, "exsentences": 2},
            headers=HEADERS, timeout=8,
        )
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", [])
        page = pages[0] if pages else {}
        if page.get("missing") or not page.get("title"):
            return {"place_name": name, "why_famous": "", **_commons_photo(name)}
        requested = set(re.findall(r"[a-z0-9]+", name.lower()))
        matched = set(re.findall(r"[a-z0-9]+", page["title"].lower()))
        if not requested.intersection(matched) or len(requested.intersection(matched)) < max(1, len(requested) - 1):
            return {}
        result = {
            "place_name": page["title"],
            "why_famous": (page.get("extract") or "").strip()[:350],
            "image_url": "",
            "image_credit": "",
            "image_page_url": "",
        }
        image_name = page.get("pageimage")
        thumbnail = page.get("thumbnail", {}).get("source", "")
        if not image_name or not thumbnail:
            result.update(_commons_photo(name))
            return result
        metadata = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={"action": "query", "format": "json", "formatversion": 2,
                    "titles": f"File:{image_name}", "prop": "imageinfo",
                    "iiprop": "extmetadata", "iiextmetadatafilter": "Artist|LicenseShortName"},
            headers=HEADERS, timeout=8,
        )
        metadata.raise_for_status()
        files = metadata.json().get("query", {}).get("pages", [])
        info = files[0].get("imageinfo", [{}])[0] if files else {}
        rights = info.get("extmetadata", {})
        artist = _plain(rights.get("Artist", {}).get("value", ""))
        license_name = _plain(rights.get("LicenseShortName", {}).get("value", ""))
        if not artist or not license_name or not thumbnail.startswith(("https://upload.wikimedia.org/", "https://thumb.wikimedia.org/")):
            result.update(_commons_photo(name))
            return result
        result["image_url"] = thumbnail
        result["image_credit"] = f"{artist[:120]} · {license_name[:60]}"
        result["image_page_url"] = "https://commons.wikimedia.org/wiki/File:" + quote(image_name.replace(" ", "_"))
        return result
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return {}


def enrich_plan(plan: TripPlan) -> TripPlan:
    enriched = plan.model_copy(deep=True)
    names = list(dict.fromkeys(activity.place_name for day in enriched.days for activity in day.activities if activity.place_name))
    with ThreadPoolExecutor(max_workers=4) as pool:
        contexts = dict(zip(names, pool.map(place_context, names)))
    for day in enriched.days:
        for activity in day.activities:
            context = contexts.get(activity.place_name, {})
            if context:
                activity.why_famous = activity.why_famous or context.get("why_famous", "")
                activity.image_url = context.get("image_url", "")
                activity.image_credit = context.get("image_credit", "")
                activity.image_page_url = context.get("image_page_url", "")
    return enriched
