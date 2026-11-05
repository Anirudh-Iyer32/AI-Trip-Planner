"""Fetch credited location photos from Wikimedia Commons for local serving."""

from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "assets" / "destinations"
TARGET.mkdir(parents=True, exist_ok=True)

FILES = {
    "varanasi.jpg": "Dashashwamedh_Ghat%2C_Ganga%2C_Varanasi.jpg",
    "jaisalmer.jpg": "Jaisalmer_goldenfort.jpg",
    "coorg.jpg": "Abbey_falls_coorg.jpg",
    "hampi.jpg": "Hampi_stone_chariot.jpg",
}

for filename, wiki_name in FILES.items():
    url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{wiki_name}?width=1400"
    request = Request(url, headers={"User-Agent": "VoyageClassProject/1.0 (destination photography)"})
    with urlopen(request, timeout=25) as response:
        content = response.read()
        content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("image/") or len(content) < 10000:
        raise RuntimeError(f"Invalid image response for {filename}: {content_type}")
    (TARGET / filename).write_bytes(content)
    print(filename, len(content), content_type)
