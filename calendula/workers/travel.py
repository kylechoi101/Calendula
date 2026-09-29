"""Travel agent: owns data/travel.json. Request type: travel. No model."""

import json
from pathlib import Path

from calendula.protocol import EXAMPLES


def load(data_dir: Path) -> dict:
    return json.loads((data_dir / "travel.json").read_text())


def handle(req: dict, data: dict) -> dict:
    # STUB: returns the protocol example. Spec logic to implement:
    # haversine miles from (req["lat"], req["lon"]) to each hospital;
    # road miles = miles * data["road_factor"]; minutes = road miles / data["avg_mph"] * 60.
    return EXAMPLES["travel"]["reply"]
