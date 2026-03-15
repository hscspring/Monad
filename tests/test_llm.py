"""Tests for core/llm.py — client creation, llm_call, timeout, error handling."""

from unittest.mock import patch, MagicMock

import pytest
import httpx

from monad.core.llm import llm_call, get_client, LLM_TIMEOUT, _client


# ---------------------------------------------------------------------------
# LLM_TIMEOUT
# ---------------------------------------------------------------------------

class TestTimeout:

    def test_timeout_values(self):
        assert LLM_TIMEOUT.connect == 15.0
        assert LLM_TIMEOUT.read == 120.0


# ---------------------------------------------------------------------------
# get_client
# ---------------------------------------------------------------------------

class TestGetClient:

    def test_returns_openai_client(self):
        import monad.core.llm as llm_mod
        llm_mod._client = None
        client = get_client()
        from openai import OpenAI
        assert isinstance(client, OpenAI)
        llm_mod._client = None

    def test_singleton(self):
        import monad.core.llm as llm_mod
        llm_mod._client = None
        c1 = get_client()
        c2 = get_client()
        assert c1 is c2
        llm_mod._client = None


# ---------------------------------------------------------------------------
# llm_call
# ---------------------------------------------------------------------------

class TestLLMCall:

    @patch("monad.core.llm.get_client")
    def test_basic_call(self, mock_gc):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "  hello world  "
        mock_client.chat.completions.create.return_value = mock_resp
        mock_gc.return_value = mock_client

        result = llm_call("test prompt")
        assert result == "hello world"

    @patch("monad.core.llm.get_client")
    def test_with_system_prompt(self, mock_gc):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "ok"
        mock_client.chat.completions.create.return_value = mock_resp
        mock_gc.return_value = mock_client

        llm_call("prompt", system="you are helpful")
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    @patch("monad.core.llm.get_client")
    def test_without_system_prompt(self, mock_gc):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "ok"
        mock_client.chat.completions.create.return_value = mock_resp
        mock_gc.return_value = mock_client

        llm_call("prompt")
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    @patch("monad.core.llm.get_client")
    def test_custom_temperature(self, mock_gc):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "ok"
        mock_client.chat.completions.create.return_value = mock_resp
        mock_gc.return_value = mock_client

        llm_call("prompt", temperature=0.9)
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["temperature"] == 0.9

    @patch("monad.core.llm.get_client")
    def test_timeout_raises(self, mock_gc):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = httpx.TimeoutException("timed out")
        mock_gc.return_value = mock_client

        with pytest.raises(Exception, match="超时"):
            llm_call("prompt")

    @patch("monad.core.llm.get_client")
    def test_api_error_raises(self, mock_gc):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")
        mock_gc.return_value = mock_client

        with pytest.raises(RuntimeError):
            llm_call("prompt")
