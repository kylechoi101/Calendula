"""Travel agent: driving distance and time from the family's ZIP to each hospital. Request type: travel.

Data: artificial_hospital_data_california.csv (hospital name -> ZIP). Drive times come from the Google Maps
Routes API when GOOGLE_MAPS_API_KEY is set, routed ZIP to ZIP: the hospitals are fictional, so Google gets
their ZIPs, and only the family's ZIP (never an address) leaves this node. Without a key (or if Google
fails) the times are a rough estimate: straight-line miles between ZIP centers (ca_zips.py) x ROAD_FACTOR
at AVG_MPH. No model: the answer is pure arithmetic, so a model call would only add latency.
"""

import csv
import json
import math
import os
import urllib.request
from pathlib import Path

from calendula.workers.ca_zips import locate

HOSPITALS = "artificial_hospital_data_california.csv"
ROUTES_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
MAX_MINUTES = 240  # a 4 h drive scores 0
ROAD_FACTOR, AVG_MPH = 1.25, 50  # rough estimate: roads are ~25% longer than a straight line

def load(data_dir: Path) -> dict:
    with open(data_dir / HOSPITALS, newline="") as f:
        return {r["Hospital Name"]: r["ZIP Code"].strip() for r in csv.DictReader(f)}


def _zip(z: str) -> dict:
    return {"waypoint": {"address": f"{z}, CA, USA"}}


def google(origin_zip: str, dest_zips: list[str]) -> list[dict | None]:
    """Driving {miles, minutes} from origin_zip to each dest ZIP (None if no route). Raises on API failure."""
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_MAPS_API_KEY is not set on this node")
    body = {"origins": [_zip(origin_zip)], "destinations": [_zip(z) for z in dest_zips], "travelMode": "DRIVE"}
    req = urllib.request.Request(ROUTES_URL, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "destinationIndex,distanceMeters,duration,condition",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            elements = json.load(resp)
    except urllib.error.HTTPError as e:  # surface Google's reason ("API key expired", "API not enabled", ...)
        body = e.read().decode(errors="replace")
        try:
            reason = (json.loads(body)[0] if body.startswith("[") else json.loads(body))["error"]["message"]
        except (ValueError, KeyError, IndexError, TypeError):
            reason = body[:200]
        raise RuntimeError(f"Google Routes {e.code}: {reason}") from None
    out: list[dict | None] = [None] * len(dest_zips)
    for e in elements:  # Google omits zero-valued fields (same ZIP -> no distanceMeters, index 0 -> no index)
        if e.get("condition") == "ROUTE_EXISTS":
            out[e.get("destinationIndex", 0)] = {"miles": round(e.get("distanceMeters", 0) / 1609.344, 1),
                                                 "minutes": round(int(e.get("duration", "0s").rstrip("s")) / 60)}
    return out


def estimate(origin_zip: str, dest_zips: list[str]) -> list[dict | None]:
    """Rough driving {miles, minutes, estimate: True} per dest ZIP (None if a ZIP can't be located)."""
    a = locate(origin_zip)
    out: list[dict | None] = []
    for z in dest_zips:
        b = locate(z)
        if not (a and b):
            out.append(None)
            continue
        p1, p2 = math.radians(a[0]), math.radians(b[0])
        h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
        miles = 3958.8 * 2 * math.asin(math.sqrt(h)) * ROAD_FACTOR
        out.append({"miles": round(miles), "minutes": round(miles / AVG_MPH * 60), "estimate": True})
    return out


def times(data: dict, origin_zip: str, hospitals: list[str]) -> dict[str, dict]:
    """{hospital: {miles, minutes}} for the hospitals we know: Google if configured, else a rough estimate."""
    known = [h for h in dict.fromkeys(hospitals) if h in data]
    if not known:
        return {}
    zips = [data[h] for h in known]
    try:
        found = google(origin_zip, zips)
    except (RuntimeError, OSError):  # no key, Google refused, or network down
        found = estimate(origin_zip, zips)
    return {h: t for h, t in zip(known, found) if t}


def note(t: dict) -> str:
    h, m = divmod(t["minutes"], 60)
    return (f"{'~' if t.get('estimate') else ''}{t['miles']} mi, about {f'{h} h {m} min' if h else f'{m} min'} drive"
            + (" (estimate)" if t.get("estimate") else ""))


def handle(req: dict, data: dict) -> dict:
    origin = str(req["case"]["zip"]).strip()
    if not (origin.isdigit() and len(origin) == 5):
        raise ValueError(f"invalid ZIP {origin!r}")
    found = times(data, origin, req["hospitals"])  # Google if configured, else the rough estimate
    return {"scores": [{"name": h, "kind": "hospital", "hospital": h,
                        "score": round(max(0.0, 1 - t["minutes"] / MAX_MINUTES), 3), "note": note(t),
                        "miles": t["miles"], "minutes": t["minutes"]}
                       for h in req["hospitals"] if (t := found.get(h))]}
