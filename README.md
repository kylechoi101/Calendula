# Calendula

**Calendula Labs**: Calendula is an AI-powered healthcare navigation system designed to help patients find
the right place for their individual treatment needs and preferences.

Finding the "best" hospital or physician is not the same for every patient. While one patient may prioritize
disease-specific expertise, another may value proximity to home, insurance coverage, hospital characteristics,
or patient experience.

Calendula combines these individual preferences with information distributed across different healthcare data
sources. Using Flower AI, we built a federated network of specialized agents that can work with decentralized
data sources without requiring all healthcare data to be centralized in one place. At the same time, we used
SuperGrid to provide the infrastructure needed. Together, they allow Calendula to integrate clinical
information, hospital data, physician expertise, insurance coverage, and patient ratings into a personalized
ranking of treatment options.

For our prototype, we demonstrate this approach using pediatric brain cancer care in California, showing how
our agentic AI model can turn fragmented healthcare information into patient-centered medical referral.

*Our vision: the right care should not only depend on what data is available, but on what matters to the
individual patient.*

- Flower Hub app: `kylechoi101/calendula`
- Run on SuperGrid: `FLWR_CHAT_SUPERLINK=supergrid FLWR_CHAT_FEDERATION=@kylechoi101/calendula uv run scripts/ask.py "<message>"`

## How it's built

Federated doctor matching on Flower: a coordinator plus five agents, each owning one dataset.
One AgentApp bundle runs on every node; `--node-config role="..."` decides which agent a SuperNode is.

## Layout and owners

| Path | What | Owner |
|---|---|---|
| `calendula/protocol.py` | Envelope, request types, one example per type. **Frozen: changes by team PR only.** | everyone |
| `calendula/app.py` | Entry point: role → worker, else coordinator | rarely touched |
| `calendula/grid.py`, `llm.py` | Flower Grid wrappers, shared model client (`llm.KIMI`, `llm.MINIMAX`) | infra |
| `calendula/workers/<role>.py` | One agent each: `PROMPT`, `load(data_dir)`, `handle(req, data) -> reply` | one per worker |
| `calendula/coordinator/intake.py` | Patient message → profile + weights | coordinator |
| `calendula/coordinator/fanout.py` | Discovery, parallel requests, timeouts | coordinator |
| `calendula/coordinator/scoring.py` | Join, filters, weighted score (pure functions) | scoring |
| `calendula/coordinator/explain.py` | Final answer text | scoring |
| `data/<role>.json` | Each agent's data (spec schemas). Currently hand-written samples. | data |
| `scripts/generate_data.py` | Seeded generator that overwrites `data/` (to be written) | data |
| `tests/` | `fake_grid.py` runs whole matches in-process, no Flower | everyone |

Every stub says `STUB:` and lists the spec logic to implement. Stubs return `protocol.EXAMPLES`, so the full
pipeline runs from day one.

## Rules

- A worker only sees `handle(req, data)`; it never imports Flower. Raise on bad input and the dispatcher replies with an error envelope.
- Data is the CSVs in `data/`. The app bundle (FAB) drops `.csv`, so workers read them from local disk via `CALENDULA_DATA_DIR` (`run_cluster.sh` sets it).
- Protocol v2 (`protocol.py`): insurance gets the insurer and returns covered hospital names; every scoring agent gets `{hospitals, case}` and returns `{"scores": [{name, kind, hospital, score 0-1, note}]}`. The coordinator takes the weighted average using the parent's priorities.
- Agents SDK with tools: never set `output_type` on an agent that has tools (MiniMax then skips the tools and invents the answer; Kimi's final JSON fails to parse). Tools write results into the run context; if the model has to produce data (scores, notes), give it a `submit_...` tool and `tool_use_behavior=StopAtTools(...)`. See `workers/doctor.py`.
- Only send an agent the fields it needs; `tests/test_coordinator.py::test_minimum_necessary` checks this.
- Secrets go in `.env` only (see `.env.example`), never in the bundle.

## Setup

Needs [uv](https://docs.astral.sh/uv/) (`brew install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
uv sync                    # creates .venv with Python 3.11 (.python-version), deps from uv.lock, pytest included
cp .env.example .env       # then fill in KIMI_API_KEY / MINIMAX_API_KEY
uv run pytest              # protocol, worker contracts, full coordinator run on the fake grid
```

Add a dependency with `uv add <pkg>` (dev-only: `uv add --dev <pkg>`) and commit `pyproject.toml` + `uv.lock` together.
Prefix commands with `uv run` or `source .venv/bin/activate` first.

## Run locally (1 SuperLink + 5 SuperNodes)

One-time: add to `~/.flwr/config.toml`
```toml
[superlink.local-deployment]
address = "127.0.0.1:9093"
insecure = true
```
Then:
```bash
./run_cluster.sh                                   # logs in logs/
uv run scripts/ask.py "I have atrial fibrillation, PLAN-B, zip 94301"   # scripted run
FLWR_CHAT_SUPERLINK=local-deployment uv run flwr chat                   # interactive; then /load .
```

## Flower 1.39 gotchas we hit

- Worker `agent.prompt` is `{"message_id","src_node_id","payload"}`; the envelope is in `payload`.
- `flwr chat` only renders `response.output_text.delta` events; `flwr log` only shows stdout. `grid.say()` does both.
- `get_nodes` returns no names locally, so the coordinator discovers roles with a `whoami` broadcast.
- The model proxy takes one `FLWR_MODEL_API_KEY` per process; the Kimi key also works for MiniMax.
- Both models are reasoning models: budget for their latency.
