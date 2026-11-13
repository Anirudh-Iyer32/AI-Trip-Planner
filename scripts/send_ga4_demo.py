"""Send clearly labeled synthetic A/B events to a separate GA4 demo cohort.

Requires GA_MEASUREMENT_ID and GA_API_SECRET in the environment. Runs as a
dry run unless --send is supplied. Never use the live voyage_ab_v1 ID here.
"""

import argparse
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request


DEMO_ID = "voyage_ab_demo_v1"


def events_for_user(index: int, rng: random.Random) -> tuple[str, list[dict]]:
    variant = "A" if index % 2 == 0 else "B"
    common = {
        "experiment_id": DEMO_ID,
        "experiment_variant": variant,
        "assignment_type": "synthetic_test",
        "test_data": "true",
        "app": "voyage",
        "session_id": 1763000000 + index,
        "engagement_time_msec": 1000,
    }
    names = ["page_view", "experiment_exposure"]
    if rng.random() < (0.60 if variant == "A" else 0.76):
        names.append("plan_started")
        if rng.random() < (0.48 if variant == "A" else 0.65):
            names.append("plan_generated")
    return variant, [{"name": name, "params": dict(common)} for name in names]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visitors", type=int, default=40)
    parser.add_argument("--send", action="store_true", help="Actually send to GA4")
    args = parser.parse_args()
    if not 2 <= args.visitors <= 100:
        parser.error("--visitors must be between 2 and 100")

    measurement_id = os.getenv("GA_MEASUREMENT_ID", "").strip()
    api_secret = os.getenv("GA_API_SECRET", "").strip()
    if args.send and (not measurement_id or not api_secret):
        parser.error("Set GA_MEASUREMENT_ID and GA_API_SECRET before --send")

    rng = random.Random(20261113)
    counts = {"A": 0, "B": 0}
    event_counts: dict[str, int] = {}
    endpoint = "https://www.google-analytics.com/mp/collect?" + urllib.parse.urlencode(
        {"measurement_id": measurement_id, "api_secret": api_secret}
    )
    for index in range(args.visitors):
        variant, events = events_for_user(index, rng)
        counts[variant] += 1
        for event in events:
            event_counts[event["name"]] = event_counts.get(event["name"], 0) + 1
        if not args.send:
            continue
        payload = json.dumps({
            "client_id": f"20261113.{100000 + index}",
            "events": events,
        }).encode()
        request = urllib.request.Request(endpoint, data=payload,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status != 204:
                    raise RuntimeError(f"GA4 returned HTTP {response.status}")
        except urllib.error.URLError as exc:
            raise SystemExit(f"Stopped after {index} visitors: {exc}") from exc
        time.sleep(0.1)

    print(json.dumps({"sent": args.send, "experiment_id": DEMO_ID,
                      "visitors": counts, "events": event_counts}, indent=2))
    if args.send:
        print("GA4 accepted the requests; report processing may take 24-48 hours.")


if __name__ == "__main__":
    main()
