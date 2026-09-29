"""Doctor agent: owns data/doctor.json. Request type: find_doctors. Uses the model."""

import json
from pathlib import Path

from calendula.protocol import EXAMPLES

PROMPT = """You score how relevant each doctor is to a patient's condition.
For every doctor, return a relevance score from 0 to 1 and a rationale of 12 words or fewer,
based only on their research_interest and surgical procedures. Reply as JSON: {"<npi>": {"relevance": .., "rationale": ".."}}."""


def load(data_dir: Path) -> dict:
    return json.loads((data_dir / "doctor.json").read_text())


def handle(req: dict, data: dict) -> dict:
    # STUB: returns the protocol example. Spec logic to implement:
    # 1. filter data["doctors"] by req["specialty"] (+ a surgical procedure if req["needs_surgery"])
    # 2. one llm.complete(PROMPT, ...) call for relevance + rationale per doctor
    # 3. fallback on model failure: keyword overlap, rationale "keyword match"
    # 4. return the top req["limit"] by relevance
    return EXAMPLES["find_doctors"]["reply"]
