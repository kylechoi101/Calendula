"""Explain: write the final answer for the patient."""

PROMPT = """You explain a ranked shortlist of doctors to a patient. For each doctor write 2 sentences
citing the numbers you are given (wait days, minutes away, network status, review quotes).
Never give medical advice. Never state a number that is not in the input."""


def explain(profile: dict, top: list[dict], filtered: list[dict], missing: list[str]) -> str:
    # STUB: template only. To implement: one llm.complete(PROMPT, ...) call with the factor breakdowns,
    # falling back to this template (top 2 factors + weakest) if the model fails.
    lines = [f"**Top doctors for {profile['condition']}:**\n"]
    for i, r in enumerate(top, 1):
        lines.append(f"{i}. **{r['name']}** ({r['hospital_id']}) — {r['rationale']}")
    lines += [f"- Filtered: {r['name']}: {r['reason']}" for r in filtered]
    if missing:
        lines.append(f"\n_Missing sources: {', '.join(missing)}_")
    return "\n".join(lines) + "\n"
