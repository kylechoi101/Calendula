"""Intake: turn the patient's chat message into a profile + weights."""

FACTORS = ["expertise", "research", "reviews", "hospital", "wait", "travel"]

PROMPT = """You turn a patient's free-text answers into a JSON profile with fields:
condition, specialty (cardiology|orthopedics|oncology), needs_surgery (bool),
urgency (routine|soon|urgent), zip, plan_id, weights (factor -> 0-5), filters {in_network_only, max_minutes}.
Never give medical advice. Leave unknown fields null."""

# The spec's demo patient. Used until intake parsing is implemented.
DEMO_PROFILE = {
    "condition": "atrial fibrillation", "specialty": "cardiology", "needs_surgery": False,
    "urgency": "soon", "lat": 37.44, "lon": -122.16, "plan_id": "PLAN-B",
    "weights": dict.fromkeys(FACTORS, 3),
    "filters": {"in_network_only": True, "max_minutes": 45},
}


def parse(prompt: str) -> dict:
    # STUB: always the demo patient. To implement: llm.complete(PROMPT, prompt), ZIP -> lat/lon lookup,
    # missing weights default to 3, and multi-turn intake via context.state.
    return DEMO_PROFILE
