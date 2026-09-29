# Calendula

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
- Agents SDK with tools: tell the model the exact JSON to reply with in the prompt, or after a tool call it answers in prose and the run falls back (`Invalid JSON when parsing model output`).
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
