"""Explain: turn the rankings into the parent's final answer."""

import json
import sys

from calendula import llm

LABELS = {"review": "doctor reputation", "hospital": "hospital quality", "travel": "distance",
          "doctor": "specialist experience"}

PROMPT = """You write the final answer of a doctor-finding service to a parent whose child has a brain
tumor. You get the case, the parent's priority weights (0-5), and rankings already computed: for each
doctor and hospital a total score (0-1) and per-factor scores with notes. Keep the given order.
Write, in warm and calm plain language:
1. one sentence acknowledging the family and what the ranking favoured (their top priorities);
2. "Top doctors": up to 5, each "N. **Name** - Hospital - match NN%" then one line on why, citing notes;
3. "Top hospitals": up to 3, one line each;
4. one line suggesting they confirm details with the hospital and their care team.
Never give medical advice. Never state a number or fact that is not in the input. Markdown, under 300 words."""

TOP_DOCTORS, TOP_HOSPITALS = 5, 3


def pct(x: float) -> str:
    return f"{round(x * 100)}%"


def template(ranking: dict) -> str:
    lines = ["Here are the options that fit your family best, based on what matters most to you.\n",
             "**Top doctors**"]
    for i, d in enumerate(ranking["doctors"][:TOP_DOCTORS], 1):
        why = "; ".join(f"{LABELS[r]}: {f['note']}" for r, f in d["factors"].items() if f["note"])
        lines.append(f"{i}. **{d['name']}** - {d['hospital']} - match {pct(d['total'])}\n   {why}")
    lines.append("\n**Top hospitals**")
    for i, h in enumerate(ranking["hospitals"][:TOP_HOSPITALS], 1):
        lines.append(f"{i}. **{h['name']}** - match {pct(h['total'])}")
    lines.append("\nPlease confirm availability and coverage details directly with the hospital and your care team.")
    return "\n".join(lines) + "\n"


def explain(case: dict, weights: dict, ranking: dict, missing: list[str]) -> str:
    if not ranking["doctors"] and not ranking["hospitals"]:
        return ("I'm sorry, I couldn't score any of the covered hospitals right now. "
                "Please try again in a moment.\n")
    def relabel(rows):
        return [r | {"factors": {LABELS[k]: f for k, f in r["factors"].items()}} for r in rows]

    facts = {"case": case, "priority_weights": {LABELS[r]: v for r, v in weights.items()},
             "rankings": {"doctors": relabel(ranking["doctors"][:TOP_DOCTORS]),
                          "hospitals": relabel(ranking["hospitals"][:TOP_HOSPITALS])}}
    try:
        text = llm.complete(PROMPT, json.dumps(facts))
    except Exception as e:  # noqa: BLE001 - template below
        print(f"[explain] model failed, using template: {e!r}", file=sys.stderr)
        text = template(ranking)
    if missing:
        text += f"\n_Not included (agent unavailable): {', '.join(LABELS.get(m, m) for m in missing)}._\n"
    return text
