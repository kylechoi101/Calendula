"""Message protocol between the coordinator and the worker agents. FROZEN: change only by team PR.

Every payload is a JSON string in a versioned envelope, and every reply uses the same envelope:
    {"v": 2, "type": "<request type>", "id": "<correlation id>", "data": {...}}
Errors are replies with type "error" and data {"message": "..."}.

Flow (v2): the coordinator asks insurance which hospitals the family's insurer covers, then sends every
scoring agent (review, hospital, travel, and doctor if online) the covered hospital names plus the case
brief. Each scoring agent replies with a 0-1 score per hospital or doctor; the coordinator takes the
weighted average using the parent's priorities.
"""

import json
from uuid import uuid4

VERSION = 2

# Request type -> required request data fields.
REQUIRED = {
    "coverage": ["insurer"],
    "reviews": ["hospitals", "case"],
    "hospitals": ["hospitals", "case"],
    "travel": ["hospitals", "case"],
    "find_doctors": ["hospitals", "case"],
    "whoami": [],
}

# Which worker role answers which request type ("whoami" is answered by every worker).
ROLE_TYPE = {
    "insurance": "coverage",
    "review": "reviews",
    "hospital": "hospitals",
    "travel": "travel",
    "doctor": "find_doctors",
}

# The case brief every scoring agent gets. Built by the coordinator once intake is complete.
CASE = {"condition": "medulloblastoma", "age": 8, "zip": "95816",
        "summary": "8-year-old with medulloblastoma, near-total resection done; needs follow-up treatment."}

# Scoring reply: one entry per hospital or doctor the agent could score.
#   name      hospital name, or doctor name when kind == "doctor"
#   kind      "hospital" | "doctor"
#   hospital  the hospital this entry belongs to (== name for kind "hospital")
#   score     0-1, higher is better for the family
#   note      one short human-readable reason, shown to the parent
DOCTOR_SCORE = {"name": "Dr. Olivia Chen", "kind": "doctor", "hospital": "Pacific Crest Medical Center",
                "score": 0.9, "note": "Google 4.6, GoodDoctor 4.9"}
HOSPITAL_SCORE = {"name": "Pacific Crest Medical Center", "kind": "hospital",
                  "hospital": "Pacific Crest Medical Center", "score": 0.8, "note": "ranked #1, 25-day wait"}

# One example request/reply per type. Tests check real replies match their keys.
EXAMPLES = {
    # An insurer the agent doesn't know is an error whose message contains "unknown insurer"; the
    # coordinator then asks the parent to check the plan name.
    "coverage": {
        "request": {"insurer": "SierraCare Health Plan"},
        "reply": {"hospitals": ["Pacific Crest Medical Center", "Golden Gate Specialty Hospital"]},
    },
    "reviews": {
        "request": {"hospitals": ["Pacific Crest Medical Center"], "case": CASE},
        "reply": {"scores": [DOCTOR_SCORE]},
    },
    "hospitals": {
        "request": {"hospitals": ["Pacific Crest Medical Center"], "case": CASE},
        "reply": {"scores": [HOSPITAL_SCORE]},
    },
    "travel": {
        "request": {"hospitals": ["Pacific Crest Medical Center"], "case": CASE},
        "reply": {"scores": [HOSPITAL_SCORE | {"score": 0.6, "note": "2 h 10 min drive"}]},
    },
    "find_doctors": {
        "request": {"hospitals": ["Pacific Crest Medical Center"], "case": CASE},
        "reply": {"scores": [DOCTOR_SCORE | {"score": 0.95, "note": "treats medulloblastoma, 8 yrs surgery"}]},
    },
    "whoami": {"request": {}, "reply": {"role": "review"}},
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
