"""Travel agent: owns data/travel.json. Request type: travel. Uses the model and Google Maps.

The agent gets drive times with a tool that calls the Google Maps Routes API (needs GOOGLE_MAPS_API_KEY).
Note: this sends the patient's lat/lon to Google. Without a key, or if Google fails, times are estimated
from straight-line distance (spec formula). Numbers in the reply come from tools, never the model.
"""

import json
import math
import os
import urllib.request
from pathlib import Path

from agents import Agent, RunContextWrapper, function_tool

from calendula import llm

PROMPT = """You find how far a patient is from hospitals. Call drive_times once with all of the
request's hospital_ids."""

ROUTES_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"


def _point(lat: float, lon: float) -> dict:
    return {"waypoint": {"location": {"latLng": {"latitude": lat, "longitude": lon}}}}


def google(lat: float, lon: float, hospitals: dict[str, dict]) -> dict[str, dict]:
    """Driving miles/minutes from (lat, lon) to each hospital via Routes API. Raises on any failure."""
    ids = list(hospitals)
    body = {"origins": [_point(lat, lon)], "travelMode": "DRIVE",
            "destinations": [_point(hospitals[h]["lat"], hospitals[h]["lon"]) for h in ids]}
    req = urllib.request.Request(ROUTES_URL, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.environ["GOOGLE_MAPS_API_KEY"],
        "X-Goog-FieldMask": "destinationIndex,distanceMeters,duration,condition",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        elements = json.load(resp)
    return {
        ids[e["destinationIndex"]]: {"miles": round(e["distanceMeters"] / 1609.344, 1),
                                     "minutes": round(int(e["duration"].rstrip("s")) / 60, 1)}
        for e in elements if e.get("condition") == "ROUTE_EXISTS"
    }


def estimate(lat: float, lon: float, h: dict, data: dict) -> dict:
    """Haversine miles x road_factor at avg_mph."""
    p1, p2 = math.radians(lat), math.radians(h["lat"])
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(h["lon"] - lon) / 2) ** 2
    road = 3958.8 * 2 * math.asin(math.sqrt(a)) * data["road_factor"]
    return {"miles": round(road, 1), "minutes": round(road / data["avg_mph"] * 60, 1)}


@function_tool
def drive_times(ctx: RunContextWrapper[dict], hospital_ids: list[str]) -> dict[str, dict]:
    """Driving miles and minutes from the patient to each hospital (Google Maps)."""
    c = ctx.context
    known = {h: c["data"]["hospitals"][h] for h in hospital_ids if h in c["data"]["hospitals"]}
    found = google(c["lat"], c["lon"], known)
    c["seen"].update(found)
    return found


# Results land in ctx["seen"]; stop right after the tool instead of asking the model to summarize.
AGENT = Agent(name="travel", instructions=PROMPT, tools=[drive_times], tool_use_behavior="stop_on_first_tool")


def load(data_dir: Path) -> dict:
    return json.loads((data_dir / "travel.json").read_text())


def handle(req: dict, data: dict) -> dict:
    lat, lon = req["lat"], req["lon"]
    ctx = {"data": data, "lat": lat, "lon": lon, "seen": {}}
    # The model never sees the patient's coordinates; drive_times reads them from ctx.
    llm.run_agent(AGENT, {"hospital_ids": req["hospital_ids"]}, ctx)
    known = {h: data["hospitals"][h] for h in req["hospital_ids"] if h in data["hospitals"]}
    missing = {h: v for h, v in known.items() if h not in ctx["seen"]}
    if missing and os.environ.get("GOOGLE_MAPS_API_KEY"):  # agent skipped or failed: call Google directly
        try:
            ctx["seen"].update(google(lat, lon, missing))
        except Exception:  # noqa: BLE001 - estimate below
            pass
    return {"travel": {h: ctx["seen"].get(h) or estimate(lat, lon, v, data) for h, v in known.items()}}
