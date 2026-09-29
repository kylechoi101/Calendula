# Agents: inputs and outputs (protocol v2)

Every request and reply is a JSON envelope `{"v": 2, "type": "<type>", "id": "...", "data": {...}}`; see
`calendula/protocol.py` for the flow and the shared `scores` reply shape. Each agent's module docstring
(`calendula/workers/<role>.py`) is the source of truth; this page summarizes them. Add a section per agent.

## Doctor (`find_doctors`)

Owns `data/artificial_pediatric_brain_cancer_doctors.csv`. Answers: which doctors at the covered hospitals have
experience with this tumor type, and how do they compare?

**Input**

| Field | Type | Example | Notes |
|---|---|---|---|
| `hospitals` | list of strings | `["Pacific Crest Medical Center", ...]` | Covered hospitals (from the Insurance agent) |
| `case` | object | `{"condition": "medulloblastoma", "age": 8, "summary": "..."}` | Only `condition` and `summary` are used |
| `weights` | object, optional | `{"Research Score": 1, "Surgical Expertise (Years)": 2, "Tumor Types Treated": 1}` | Set by the orchestrator. Rescaled to sum to 1; a metric left out gets 0; none → equal. Unknown, negative or all-zero → error reply. |

**Output** — `{"scores": [{"name", "kind": "doctor", "hospital", "score", "note"}, ...]}`, best first:

```json
{"name": "Dr. Isabella Martinez", "kind": "doctor", "hospital": "Golden Gate Specialty Hospital",
 "score": 0.844, "note": "treats medulloblastoma, 30 yrs surgery, research 8.3"}
```

**Algorithm**

1. **Tumor type.** Exact names (`medulloblastoma`, `pediatric high-grade glioma`, `ependymoma`) and aliases
   (`high-grade glioma`, `pediatric hgg`, `hgg`) map directly, with no model call. Other wording ("DIPG", "posterior
   fossa tumor") goes to the model (`llm.DEFAULT`, MiniMax; Kimi also verified), which records its choice with the
   `select_tumor_type` tool; the run stops at that tool call. No match → error reply `unknown condition`.
2. **Filter.** Doctors with experience in that tumor type at a covered hospital. None → `{"scores": []}`.
3. **Scale.** Each metric — `Research Score`, `Surgical Expertise (Years)`, `Tumor Types Treated` (how many of the
   three tumor types the doctor treats) — is min-max scaled within those doctors (best = 1, all equal → 0.5).
4. **Weight.** Score = weighted sum of the scaled metrics, in 0–1. Sorted best first; ties by Doctor ID.

Numbers come only from the CSV, never the model. `Doctor ID`, `Hospital Ranking`, `Hospital Affiliated` and the
experience flags stay on the node.
