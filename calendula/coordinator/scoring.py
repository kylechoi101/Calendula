"""Combine the scoring agents' replies into rankings. Pure functions, no Flower, no model.

Every agent returns 0-1 scores per hospital or per doctor (protocol "scores" replies). A doctor inherits
its hospital's hospital-level scores (quality, distance); the total is the weighted average of whatever
scores exist, using the parent's weights, so a silent agent just drops out of the average.
"""

HOSPITAL_ROLES = ("hospital", "travel")
DOCTOR_ROLES = ("review", "doctor")


def weighted(factors: dict[str, dict], w: dict[str, float]) -> float | None:
    used = {r: f["score"] for r, f in factors.items() if w.get(r, 0) > 0}
    total = sum(w[r] for r in used)
    return round(sum(w[r] * s for r, s in used.items()) / total, 3) if total else None


def rank(covered: list[str], replies: dict[str, dict | None], w: dict[str, float]) -> dict:
    """Returns {"doctors": [...], "hospitals": [...]}, best first. Each row has "total" and per-role "factors"."""
    hospitals = {h: {"name": h, "factors": {}} for h in covered}
    doctors: dict[tuple[str, str], dict] = {}
    for role, reply in replies.items():
        for s in (reply or {}).get("scores") or []:
            try:
                f = {"score": min(max(float(s["score"]), 0.0), 1.0), "note": str(s.get("note") or "")}
                name, kind, hosp = str(s["name"]), s["kind"], s["hospital"]
            except (KeyError, TypeError, ValueError):  # a malformed entry is dropped, not fatal
                continue
            if not isinstance(hosp, str) or hosp not in hospitals or kind not in ("hospital", "doctor"):
                continue  # only covered hospitals count
            if kind == "hospital":
                hospitals[hosp]["factors"][role] = f
            else:
                d = doctors.setdefault((name, hosp), {"name": name, "hospital": hosp, "factors": {}})
                d["factors"][role] = f

    if replies.get("doctor") is not None:  # the doctor agent lists who treats this tumor; nobody else qualifies
        doctors = {k: d for k, d in doctors.items() if "doctor" in d["factors"]}
    for d in doctors.values():
        d["factors"] = hospitals[d["hospital"]]["factors"] | d["factors"]
    for h in hospitals.values():  # a hospital's reputation factor is the mean of its doctors' reviews
        revs = [d["factors"]["review"]["score"] for d in doctors.values()
                if d["hospital"] == h["name"] and "review" in d["factors"]]
        if revs:
            h["factors"]["review"] = {"score": sum(revs) / len(revs), "note": f"avg of {len(revs)} doctors"}

    def ranked(rows):
        for r in rows:
            r["total"] = weighted(r["factors"], w)
        return sorted((r for r in rows if r["total"] is not None), key=lambda r: -r["total"])

    return {"doctors": ranked(list(doctors.values())), "hospitals": ranked(list(hospitals.values()))}
