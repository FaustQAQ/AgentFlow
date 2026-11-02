import json

import httpx
import pytest

from app.services.llm.client import DeepSeekClient, LLMAPIError, LLMTimeoutError


def test_deepseek_client_parses_tool_calls() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "demo",
                                        "arguments": json.dumps({"x": 1}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    client = DeepSeekClient(
        "test-key",
        "https://example.test",
        "deepseek-chat",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    response = client.chat([{"role": "user", "content": "hi"}], [])
    assert response.tool_calls[0].name == "demo"
    assert response.tool_calls[0].arguments == {"x": 1}


def test_missing_api_key_fails_without_network() -> None:
    with pytest.raises(LLMAPIError):
        DeepSeekClient("", "https://example.test", "model").chat([], [])


def test_timeout_is_classified() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    client = DeepSeekClient(
        "key",
        "https://example.test",
        "model",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(LLMTimeoutError):
        client.chat([], [])
