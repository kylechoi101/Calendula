"""Join worker replies and rank candidates. Pure functions, no Flower, no model."""


def join(doctors: dict, review=None, hospital=None, insurance=None, travel=None) -> list[dict]:
    """One row per candidate NPI. A source that didn't reply (None) leaves its fields None."""
    rows = []
    for d in doctors["doctors"]:
        h = d["hospital_id"]
        rows.append({
            **d,
            "review": review["reviews"].get(d["npi"]) if review else None,
            "hospital": hospital["hospitals"].get(h) if hospital else None,
            "in_network": insurance["coverage"].get(h) if insurance else None,
            "travel": travel["travel"].get(h) if travel else None,
        })
    return rows


def rank(rows: list[dict], profile: dict) -> tuple[list[dict], list[dict]]:
    """Returns (top 3, filtered-out rows with a "reason")."""
    # STUB: sorts by relevance only. Spec logic to implement: hard filters, min-max normalized
    # factors (all-equal column -> 0.5), weighted score with renormalization for missing factors,
    # urgent doubles the wait weight, per-factor breakdown kept on each row.
    return sorted(rows, key=lambda r: r["relevance"], reverse=True)[:3], []
