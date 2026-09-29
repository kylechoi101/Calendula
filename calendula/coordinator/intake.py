"""Intake: read the whole chat, extract the case, and ask warm follow-ups until nothing is missing.

The model extracts fields and writes the follow-up; the code decides what is still missing, so a model
slip can't start the search early. Without the model, a keyword fallback does the extraction.
"""

import re

from agents import Agent
from pydantic import BaseModel

from calendula import llm

# Parent's priority name -> the scoring agent (role) it weights.
PRIORITIES = {"doctor_reputation": "review", "hospital_quality": "hospital",
              "distance": "travel", "specialist_experience": "doctor"}


class Priorities(BaseModel):
    doctor_reputation: int
    hospital_quality: int
    distance: int
    specialist_experience: int


class Profile(BaseModel):
    child_name: str | None
    age: int | None
    condition: str | None
    summary: str | None
    zip: str | None
    insurer: str | None
    priorities: Priorities | None
    follow_up: str


PROMPT = """You are the intake assistant of a doctor-finding service for families of children with brain
tumors. You get the whole conversation so far. Extract:
- child_name, age: if given.
- condition: the diagnosis in plain words, e.g. "medulloblastoma", "high-grade glioma", "ependymoma".
- summary: 1-2 sentences of the medical situation (diagnosis, treatment so far, what they need next),
  without names, using only facts the parent gave; don't add medical terms they didn't use.
- zip: the family's 5-digit ZIP code.
- insurer: the insurance company or plan name, as the parent wrote it.
- priorities: 0-5 for each of doctor_reputation, hospital_quality, distance, specialist_experience,
  from what the parent says matters to them. Only fill this once the parent has said what matters; if
  they say everything matters or they don't mind, use 3 for all.
Use null for anything not yet given. Never guess a ZIP or an insurer.

Then write follow_up: if anything is null among condition, zip, insurer, priorities, a short, warm,
empathetic reply to the parent that acknowledges what they shared and asks for what is missing (at
most two things at a time; ask what matters most to them in plain words, e.g. doctors' reputation,
hospital quality, being close to home, the specialist's experience). If nothing is missing, "".
Never give medical advice."""

AGENT = Agent(name="intake", instructions=PROMPT, output_type=Profile)

REQUIRED = {"condition": "your child's diagnosis", "zip": "your ZIP code",
            "insurer": "your insurance provider", "priorities": "what matters most to you in choosing care"}

CONDITIONS = ["medulloblastoma", "high-grade glioma", "glioma", "ependymoma"]
PRIORITY_WORDS = {
    "doctor_reputation": ["review", "rating", "reputation", "bedside", "kind"],
    "hospital_quality": ["hospital", "outcome", "ranking", "best care", "quality"],
    "distance": ["close", "near", "distance", "drive", "far", "home"],
    "specialist_experience": ["experience", "specialist", "expert", "surgeon"],
}


def missing(p: dict) -> list[str]:
    return [k for k in REQUIRED if not p.get(k)]


def fallback(turns: list[dict]) -> dict:
    """Keyword extraction from the parent's messages, for when the model is unavailable."""
    text = " ".join(t["text"] for t in turns if t["role"] == "user")
    low = text.lower()
    zips = re.findall(r"\b9\d{4}\b", text)
    insurer = re.search(r"\b((?:[A-Z][A-Za-z]+ ){1,3}(?:Health Plan|Health|Assurance|Insurance|Coverage|"
                        r"Partners|Network|Plan))\b", text)
    hits = {k: sum(w in low for w in words) for k, words in PRIORITY_WORDS.items()}
    return {
        "condition": next((c for c in CONDITIONS if c in low), None),
        "summary": None,
        "zip": zips[-1] if zips else None,
        "insurer": insurer.group(1) if insurer else None,
        "priorities": {k: 5 if n else 2 for k, n in hits.items()} if any(hits.values()) else None,
        "follow_up": "",
    }


def gather(turns: list[dict]) -> dict:
    """Profile dict from the chat so far; "missing" lists what to ask for, "follow_up" the question."""
    out = llm.run_agent(AGENT, {"conversation": turns}, {})
    p = out.model_dump() if out else fallback(turns)
    if p.get("zip") and not re.fullmatch(r"\d{5}", p["zip"]):
        p["zip"] = None
    p["missing"] = missing(p)
    if p["missing"] and not p.get("follow_up"):
        p["follow_up"] = ("I'm so sorry you and your family are going through this. I'm here to help you find "
                          "the right care. Could you tell me " + " and ".join(REQUIRED[k] for k in p["missing"][:2])
                          + "?")
    return p


def weights(p: dict) -> dict[str, float]:
    """Parent's priorities as {role: weight}; unstated ones default to 3."""
    pr = p.get("priorities") or {}
    return {role: float(pr.get(name, 3)) for name, role in PRIORITIES.items()}


def case(p: dict) -> dict:
    """The case brief sent to the scoring agents (protocol.CASE shape)."""
    summary = p.get("summary") or f"{p.get('age') or 'A'}-year-old child with {p['condition']}."
    return {"condition": p["condition"], "age": p.get("age"), "zip": p["zip"], "summary": summary}


def recap(p: dict) -> str:
    """The summary the parent sees before the search starts."""
    who = p.get("child_name") or "your child"
    age = f", age {p['age']}" if p.get("age") else ""
    top = sorted((p.get("priorities") or {}).items(), key=lambda kv: -kv[1])
    cares = ", ".join(k.replace("_", " ") for k, v in top if v >= 4) or "a balance of everything"
    return (f"Thank you for sharing all of this. Here's what I understand:\n\n"
            f"- **Patient:** {who}{age}\n- **Diagnosis:** {p['condition']}\n"
            + (f"- **Situation:** {p['summary']}\n" if p.get("summary") else "")
            + f"- **Home ZIP:** {p['zip']}\n- **Insurance:** {p['insurer']}\n"
            f"- **What matters most:** {cares}\n\n"
            "Looking for the best personalized medical service for you.\n\n")
