"""Hospital agent: owns data/hospital.json. Request type: hospitals. No model."""

import json
from pathlib import Path

from calendula.protocol import EXAMPLES


def load(data_dir: Path) -> dict:
    return json.loads((data_dir / "hospital.json").read_text())


def handle(req: dict, data: dict) -> dict:
    # STUB: returns the protocol example. Spec logic to implement:
    # look up each id in req["hospital_ids"]; return ranking, ratio, wait_days[req["specialty"]],
    # and outcomes[req["condition"]] (mortality, case_volume: null when there's no data).
    return EXAMPLES["hospitals"]["reply"]
