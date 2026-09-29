"""Shared model client.

Calls go through Flower Runtime, which forwards them to FLWR_MODEL_API_ENDPOINT with FLWR_MODEL_API_KEY.
Both must be set in the env of every SuperLink/SuperNode that runs a model-using agent (see .env.example).
"""

import json
import os
import sys

import httpx
from agents import Agent, OpenAIResponsesModel, RunConfig, Runner
from openai import AsyncOpenAI, OpenAI

KIMI = "dedicated/flowerai/Kimi-K2.7-Code-1OUHWL"
MINIMAX = "dedicated/flowerai/MiniMax-M3-OOLI9o"
DEFAULT = MINIMAX


def complete(instructions: str, prompt: str, model: str = DEFAULT, timeout: float = 60) -> str:
    """One non-streaming model call. Raises on failure; callers own their fallback."""
    client = OpenAI(
        base_url=os.environ["FLWR_RUNTIME_BASE_URL"],
        api_key=os.environ["FLWR_RUNTIME_API_KEY"],
        max_retries=0,
        timeout=timeout,
    )
    return client.responses.create(model=model, instructions=instructions, input=prompt).output_text


# Flower Runtime's /responses proxy rejects any field outside this set (flwr 1.39, routers/runtime/responses.py);
# the Agents SDK always sends a few more (e.g. "include": []), so they're dropped before the request leaves.
PROXY_FIELDS = {"model", "input", "stream", "tools", "tool_choice", "reasoning", "previous_response_id",
                "instructions", "max_output_tokens", "metadata", "text"}


class _ProxyTransport(httpx.AsyncHTTPTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/responses"):
            body = {k: v for k, v in json.loads(request.content).items() if k in PROXY_FIELDS}
            headers = {k: v for k, v in request.headers.items() if k.lower() != "content-length"}
            request = httpx.Request("POST", request.url, headers=headers, content=json.dumps(body).encode(),
                                    extensions=request.extensions)  # carries the timeout
        return await super().handle_async_request(request)


def run_agent(agent: Agent, req: dict, context: dict, model: str = DEFAULT, timeout: float = 60):
    """Run a worker agent (OpenAI Agents SDK) over its request. Tools get `context` via ctx.context.

    Returns the agent's final_output, or None if the model or tool loop fails; callers own their fallback.
    """
    try:
        client = AsyncOpenAI(
            base_url=os.environ["FLWR_RUNTIME_BASE_URL"],
            api_key=os.environ["FLWR_RUNTIME_API_KEY"],
            max_retries=0,
            timeout=timeout,
            http_client=httpx.AsyncClient(transport=_ProxyTransport(), timeout=timeout),
        )
        # Explicit model object: the SDK would parse a plain "dedicated/..." string as a provider prefix.
        # Tracing off: the SDK uploads traces to OpenAI by default, and these carry private data.
        config = RunConfig(model=OpenAIResponsesModel(model, client), tracing_disabled=True)
        result = Runner.run_sync(agent, json.dumps(req), context=context, max_turns=10, run_config=config)
        return result.final_output
    except Exception as e:  # noqa: BLE001 - any failure means "use the fallback"
        print(f"[{agent.name}] agent failed, using fallback: {e!r}", file=sys.stderr)
        return None
