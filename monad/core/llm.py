"""
MONAD LLM Client
Shared LLM calling utility using OpenAI-compatible API.
"""

import time

import httpx
from loguru import logger
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from monad.config import (
    CONFIG, TIMEOUT_LLM_CONNECT, TIMEOUT_LLM_READ,
    TIMEOUT_LLM_WRITE, TIMEOUT_LLM_POOL,
    LLM_MAX_RETRIES, LLM_RETRY_BASE_DELAY, LLM_RETRY_MAX_DELAY,
    TRUNCATE_MEDIUM, truncate,
)
from monad.interface.output import Output

_client = None

LLM_TIMEOUT = httpx.Timeout(
    connect=TIMEOUT_LLM_CONNECT,
    read=TIMEOUT_LLM_READ,
    write=TIMEOUT_LLM_WRITE,
    pool=TIMEOUT_LLM_POOL,
)


def _is_retryable(exc: Exception) -> bool:
    """Decide if an exception is transient and worth retrying."""
    if isinstance(exc, (httpx.TimeoutException, APITimeoutError, APIConnectionError)):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        return True
    err_msg = str(exc).lower()
    if any(k in err_msg for k in ("502", "503", "504", "gateway", "timeout", "connection")):
        return True
    return False


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


def llm_call(prompt: str, system: str = "", temperature: float = None,
             max_tokens: int = None) -> str:
    """Make an LLM call with automatic retry on transient failures.

    Retries up to LLM_MAX_RETRIES times with exponential backoff for
    timeouts, connection errors, and 5xx status codes.

    Raises:
        Exception with human-readable message on persistent failure
    """
    client = get_client()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    last_exc = None
    for attempt in range(1 + LLM_MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=CONFIG.llm.model,
                messages=messages,
                temperature=temperature if temperature is not None else CONFIG.llm.temperature,
                max_tokens=max_tokens or CONFIG.llm.max_tokens,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            last_exc = e
            if not _is_retryable(e) or attempt >= LLM_MAX_RETRIES:
                break
            delay = min(LLM_RETRY_BASE_DELAY * (2 ** attempt), LLM_RETRY_MAX_DELAY)
            Output.warn(f"LLM API 瞬时错误 (第{attempt + 1}次)，{delay:.0f}s 后重试...")
            logger.warning(f"LLM transient error (attempt {attempt + 1}/{LLM_MAX_RETRIES}): {e}")
            time.sleep(delay)

    if isinstance(last_exc, (httpx.TimeoutException, APITimeoutError)):
        Output.error(f"LLM API 调用超时 ({TIMEOUT_LLM_READ:.0f}s)，已重试 {LLM_MAX_RETRIES} 次")
        raise Exception("LLM API 调用超时（已重试）")

    logger.error(f"LLM API error after {LLM_MAX_RETRIES} retries: {last_exc}")
    Output.error(f"LLM API 错误: {truncate(str(last_exc), TRUNCATE_MEDIUM)}")
    raise last_exc
