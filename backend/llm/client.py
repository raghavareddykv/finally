"""LiteLLM client for calling the LLM via OpenRouter/Cerebras."""

from __future__ import annotations

import logging

from litellm import completion

from .models import LLMResponse

logger = logging.getLogger(__name__)

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY: dict = {"provider": {"order": ["cerebras"]}}


async def call_llm(messages: list[dict[str, str]]) -> LLMResponse:
    """Call the LLM and return a parsed structured response.

    Raises
    ------
    ValueError
        If the LLM response cannot be parsed into the expected schema.
    Exception
        Propagates LiteLLM/network errors to the caller for graceful handling.
    """
    response = completion(
        model=MODEL,
        messages=messages,
        response_format=LLMResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
    )

    raw_content = response.choices[0].message.content
    logger.debug("LLM raw response: %s", raw_content)

    try:
        return LLMResponse.model_validate_json(raw_content)
    except Exception as exc:
        logger.error("Failed to parse LLM response: %s | Raw: %s", exc, raw_content)
        raise ValueError(f"LLM returned invalid structured output: {exc}") from exc
