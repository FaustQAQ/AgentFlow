import json
from dataclasses import dataclass
from typing import Any

import httpx


class LLMError(Exception):
    """Base class for LLM client failures."""


class LLMTimeoutError(LLMError):
    """Raised when the LLM request times out."""


class LLMAPIError(LLMError):
    """Raised when the LLM API returns an error or invalid response."""


@dataclass(frozen=True)
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    content: str | None
    tool_calls: list[LLMToolCall]
    assistant_message: dict[str, Any]


class DeepSeekClient:
    """Small OpenAI-compatible DeepSeek Chat Completions client."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 30,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMAPIError("LLM API key is not configured")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tool_choice": "auto" if tools else "none",
        }
        if tools:
            payload["tools"] = tools
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        try:
            if self.http_client is not None:
                response = self.http_client.post(
                    url, json=payload, headers=headers, timeout=self.timeout_seconds
                )
            else:
                response = httpx.post(
                    url, json=payload, headers=headers, timeout=self.timeout_seconds
                )
        except httpx.TimeoutException as error:
            raise LLMTimeoutError("DeepSeek request timed out") from error
        except httpx.HTTPError as error:
            raise LLMAPIError(f"DeepSeek request failed: {error}") from error

        if response.is_error:
            raise LLMAPIError(
                f"DeepSeek API returned HTTP {response.status_code}: {response.text[:500]}"
            )
        try:
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            raw_calls = message.get("tool_calls") or []
            calls = []
            for raw_call in raw_calls:
                function = raw_call["function"]
                calls.append(
                    LLMToolCall(
                        id=str(raw_call["id"]),
                        name=str(function["name"]),
                        arguments=json.loads(function.get("arguments", "{}")),
                    )
                )
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise LLMAPIError("DeepSeek returned an invalid chat completion") from error

        return LLMResponse(
            content=message.get("content"),
            tool_calls=calls,
            assistant_message=message,
        )
