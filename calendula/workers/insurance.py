"""Insurance agent: owns data/insurance.json. Request type: coverage. No model."""

import json
from pathlib import Path

from calendula.protocol import EXAMPLES


def load(data_dir: Path) -> dict:
    return json.loads((data_dir / "insurance.json").read_text())


def handle(req: dict, data: dict) -> dict:
    # STUB: returns the protocol example. Spec logic to implement:
    # in_network = hospital_id in data["plans"][req["plan_id"]]; unknown plan -> raise ValueError
    # (the dispatcher turns exceptions into an error envelope).
    return EXAMPLES["coverage"]["reply"]
