"""Shared model client.

Calls go through Flower Runtime, which forwards them to FLWR_MODEL_API_ENDPOINT with FLWR_MODEL_API_KEY.
Both must be set in the env of every SuperLink/SuperNode that runs a model-using agent (see .env.example).
"""

import os

from openai import OpenAI

KIMI = "dedicated/flowerai/Kimi-K2.7-Code-1OUHWL"
MINIMAX = "dedicated/flowerai/MiniMax-M3-OOLI9o"
DEFAULT = KIMI


def complete(instructions: str, prompt: str, model: str = DEFAULT, timeout: float = 60) -> str:
    """One non-streaming model call. Raises on failure; callers own their fallback."""
    client = OpenAI(
        base_url=os.environ["FLWR_RUNTIME_BASE_URL"],
        api_key=os.environ["FLWR_RUNTIME_API_KEY"],
        max_retries=0,
        timeout=timeout,
    )
    return client.responses.create(model=model, instructions=instructions, input=prompt).output_text
