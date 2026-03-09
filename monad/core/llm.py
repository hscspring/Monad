"""
MONAD LLM Client
Shared LLM calling utility using OpenAI-compatible API.
Includes timeout handling to prevent hanging.
"""

import httpx
from openai import OpenAI
from monad.config import CONFIG
from monad.interface.output import Output


_client = None

# Timeout: 60 seconds for connection, 120 seconds for response
LLM_TIMEOUT = httpx.Timeout(connect=15.0, read=120.0, write=15.0, pool=15.0)


def get_client() -> OpenAI:
    """Get or create the OpenAI client with timeout."""
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=CONFIG.llm.base_url,
            api_key=CONFIG.llm.api_key,
            timeout=LLM_TIMEOUT,
        )
    return _client


def llm_call(prompt: str, system: str = "", temperature: float = None, max_tokens: int = None) -> str:
    """Make a single LLM call and return the response text.

    Args:
        prompt: The user prompt
        system: Optional system prompt
        temperature: Override default temperature
        max_tokens: Override default max_tokens

    Raises:
        Exception with human-readable message on timeout or API error
    """
    client = get_client()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=CONFIG.llm.model,
            messages=messages,
            temperature=temperature if temperature is not None else CONFIG.llm.temperature,
            max_tokens=max_tokens or CONFIG.llm.max_tokens,
        )
        return response.choices[0].message.content.strip()

    except httpx.TimeoutException:
        Output.error("LLM API 调用超时 (120s)，请检查网络或 API 服务状态")
        raise Exception("LLM API 调用超时")
    except Exception as e:
        Output.error(f"LLM API 错误: {str(e)[:200]}")
        raise
