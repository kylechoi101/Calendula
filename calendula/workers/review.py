"""Review agent: owns data/review.json. Request type: reviews. Uses the model."""

import json
from pathlib import Path

from calendula.protocol import EXAMPLES

PROMPT = """You read patient reviews of doctors. For each NPI, score empathy from 0 to 1
(listening, explaining, respect) and pick one representative quote of 20 words or fewer.
Reply as JSON: {"<npi>": {"empathy": .., "quote": ".."}}."""


def load(data_dir: Path) -> dict:
    return json.loads((data_dir / "review.json").read_text())


def handle(req: dict, data: dict) -> dict:
    # STUB: returns the protocol example. Spec logic to implement:
    # 1. avg_rating and n per NPI in req["npis"]
    # 2. one batched llm.complete(PROMPT, ...) call; cap 5 reviews per NPI, 15 NPIs per call
    # 3. fallback: empathy = (avg_rating - 1) / 4, quote = most recent review
    return EXAMPLES["reviews"]["reply"]
