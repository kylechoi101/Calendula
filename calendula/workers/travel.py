"""Travel agent: driving distance and time from the family's ZIP to each hospital. Request type: travel.

Data: artificial_hospital_data_california.csv (hospital name -> ZIP). Drive times come from the Google Maps
Routes API (needs GOOGLE_MAPS_API_KEY), routed ZIP to ZIP: the hospitals are fictional, so Google gets
their ZIPs, and only the family's ZIP (never an address) leaves this node. Numbers come from the tool,
never the model; without Google the agent errors and the coordinator ranks without distance.
"""

import csv
import json
import os
import urllib.request
from pathlib import Path

from agents import Agent, RunContextWrapper, function_tool

from calendula import llm

HOSPITALS = "artificial_hospital_data_california.csv"
ROUTES_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
MAX_MINUTES = 240  # a 4 h drive scores 0

PROMPT = """You find how far a family lives from hospitals. Call drive_times once with the hospital
names you need (all of the request's hospitals, or the ones the question is about)."""


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


def times(data: dict, origin_zip: str, hospitals: list[str]) -> dict[str, dict]:
    """{hospital: {miles, minutes}} for the hospitals we know and Google can route to."""
    known = [h for h in dict.fromkeys(hospitals) if h in data]
    if not known:
        return {}
    return {h: t for h, t in zip(known, google(origin_zip, [data[h] for h in known])) if t}


@function_tool
def drive_times(ctx: RunContextWrapper[dict], hospitals: list[str]) -> dict[str, dict]:
    """Driving miles and minutes from the family's home to each named hospital (Google Maps)."""
    c = ctx.context
    found = times(c["data"], c["zip"], hospitals)
    c["seen"].update(found)
    return found


AGENT = Agent(name="travel", instructions=PROMPT, tools=[drive_times], tool_use_behavior="stop_on_first_tool")


def note(t: dict) -> str:
    h, m = divmod(t["minutes"], 60)
    return f"{t['miles']} mi, about {f'{h} h {m} min' if h else f'{m} min'} drive"


def handle(req: dict, data: dict) -> dict:
    origin = str(req["case"]["zip"]).strip()
    if not (origin.isdigit() and len(origin) == 5):
        raise ValueError(f"invalid ZIP {origin!r}")
    ctx = {"data": data, "zip": origin, "seen": {}}
    # The model never sees the family's ZIP; drive_times reads it from ctx.
    llm.run_agent(AGENT, {"hospitals": req["hospitals"]}, ctx)
    missing = [h for h in req["hospitals"] if h not in ctx["seen"]]
    if missing:  # agent skipped or failed: call Google directly (raises if Google is down or unconfigured)
        ctx["seen"].update(times(data, origin, missing))
    return {"scores": [{"name": h, "kind": "hospital", "hospital": h,
                        "score": round(max(0.0, 1 - t["minutes"] / MAX_MINUTES), 3), "note": note(t),
                        "miles": t["miles"], "minutes": t["minutes"]}
                       for h in req["hospitals"] if (t := ctx["seen"].get(h))]}
