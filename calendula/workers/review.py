"""Review agent: owns data/review.json. Request type: reviews. Uses the model.

The agent reads reviews through a tool and judges empathy; avg_rating and n are computed from data.
"""

import json
from pathlib import Path

from agents import Agent, RunContextWrapper, function_tool
from pydantic import BaseModel

from calendula import llm

PROMPT = """You read patient reviews of doctors. For every NPI in the request, call get_reviews, then
score empathy from 0 to 1 (listening, explaining, respect) and pick one representative quote of
20 words or fewer, copied verbatim from a review."""


class Judgment(BaseModel):
    npi: str
    empathy: float
    quote: str


class Judgments(BaseModel):
    judgments: list[Judgment]


def recent(data: dict, npi: str, n: int = 5) -> list[dict]:
    return sorted(data["reviews"].get(npi, []), key=lambda r: r["date"], reverse=True)[:n]


@function_tool
def get_reviews(ctx: RunContextWrapper[dict], npi: str) -> list[dict]:
    """The 5 most recent reviews (rating 1-5, date, text) for one doctor NPI."""
    return [{"rating": r["rating"], "date": r["date"], "text": r["text"]} for r in recent(ctx.context["data"], npi)]


AGENT = Agent(name="review", instructions=PROMPT, tools=[get_reviews], output_type=Judgments)


def load(data_dir: Path) -> dict:
    return json.loads((data_dir / "review.json").read_text())


def handle(req: dict, data: dict) -> dict:
    # ponytail: one agent run for all NPIs; batch in 15s (spec) if requests get large.
    out = llm.run_agent(AGENT, req, {"data": data})
    judged = {j.npi: j for j in out.judgments} if out else {}
    reviews = {}
    for npi in req["npis"]:
        rs = data["reviews"].get(npi, [])
        if not rs:
            continue
        avg = sum(r["rating"] for r in rs) / len(rs)
        latest = recent(data, npi, 1)[0]["text"]
        j = judged.get(npi)
        # A quote must really appear in a review; otherwise use the most recent one.
        quote = j.quote if j and any(j.quote in r["text"] for r in rs) else latest
        reviews[npi] = {"avg_rating": round(avg, 2), "n": len(rs), "quote": quote,
                        "empathy": min(max(j.empathy, 0.0), 1.0) if j else round((avg - 1) / 4, 2)}
    return {"reviews": reviews}
