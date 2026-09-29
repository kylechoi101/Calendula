"""Message protocol between the coordinator and the five worker agents. FROZEN: change only by team PR.

Every payload is a JSON string in a versioned envelope, and every reply uses the same envelope:
    {"v": 1, "type": "<request type>", "id": "<correlation id>", "data": {...}}
Errors are replies with type "error" and data {"message": "..."}.
"""

import json
from uuid import uuid4

VERSION = 1

# Request type -> required request data fields.
REQUIRED = {
    "find_doctors": ["condition", "specialty", "needs_surgery", "limit"],
    "reviews": ["npis"],
    "hospitals": ["hospital_ids", "condition", "specialty"],
    "coverage": ["plan_id", "hospital_ids"],
    "travel": ["lat", "lon", "hospital_ids"],
    "whoami": [],
}

# Which worker role answers which request type ("whoami" is answered by every worker).
ROLE_TYPE = {
    "doctor": "find_doctors",
    "review": "reviews",
    "hospital": "hospitals",
    "insurance": "coverage",
    "travel": "travel",
}

# One example request/reply per type. Stub workers return these; tests check real replies match their keys.
EXAMPLES = {
    "find_doctors": {
        "request": {"condition": "atrial fibrillation", "specialty": "cardiology", "needs_surgery": False, "limit": 15},
        "reply": {"doctors": [{
            "npi": "1000000001", "name": "Dr. Maya Chen", "specialty": "cardiology", "hospital_id": "H1",
            "accepting_new_patients": True, "expertise": 8.5, "research_score": 9.1,
            "relevance": 0.93, "rationale": "leads AFib catheter ablation outcomes research",
        }]},
    },
    "reviews": {
        "request": {"npis": ["1000000001"]},
        "reply": {"reviews": {"1000000001": {
            "avg_rating": 4.2, "n": 6, "empathy": 0.71, "quote": "Took time to explain my options.",
        }}},
    },
    "hospitals": {
        "request": {"hospital_ids": ["H1"], "condition": "atrial fibrillation", "specialty": "cardiology"},
        "reply": {"hospitals": {"H1": {
            "name": "Bayview Heart Institute", "ranking": 1, "doctor_patient_ratio": 0.21,
            "mortality": 0.82, "case_volume": 1450, "wait_days": 42,
        }}},
    },
    "coverage": {
        "request": {"plan_id": "PLAN-B", "hospital_ids": ["H1", "H3"]},
        "reply": {"coverage": {"H1": False, "H3": True}},
    },
    "travel": {
        "request": {"lat": 37.44, "lon": -122.16, "hospital_ids": ["H1"]},
        "reply": {"travel": {"H1": {"miles": 1.1, "minutes": 2.9}}},
    },
    "whoami": {"request": {}, "reply": {"role": "doctor"}},
}


class ProtocolError(ValueError):
    pass


def envelope(type_: str, data: dict, id_: str | None = None) -> dict:
    return {"v": VERSION, "type": type_, "id": id_ or uuid4().hex[:12], "data": data}


def error(message: str, id_: str | None = None) -> dict:
    return envelope("error", {"message": message}, id_)


def parse(text: str) -> dict:
    """Parse and validate a request envelope; raises ProtocolError on anything malformed."""
    try:
        env = json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        raise ProtocolError(f"payload is not JSON: {e}") from None
    if not isinstance(env, dict) or env.get("v") != VERSION:
        raise ProtocolError(f"expected envelope with v={VERSION}")
    if env.get("type") not in REQUIRED:
        raise ProtocolError(f"unknown request type {env.get('type')!r}")
    data = env.get("data")
    if not isinstance(data, dict):
        raise ProtocolError("data must be an object")
    missing = [f for f in REQUIRED[env["type"]] if f not in data]
    if missing:
        raise ProtocolError(f"{env['type']}: missing fields {missing}")
    return env
