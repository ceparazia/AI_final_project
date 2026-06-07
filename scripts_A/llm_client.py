from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]+")


@dataclass
class LLMResult:
    content: str
    used_api: bool
    error: str | None = None


class DeepSeekClient:
    """Small dependency-free client for DeepSeek's OpenAI-compatible API."""

    def __init__(
        self,
        model: str = "deepseek-v4-flash",
        base_url: str = "https://api.deepseek.com",
        timeout: int = 25,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = load_api_key()

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.45) -> LLMResult:
        if not self.api_key:
            return LLMResult("", False, "DEEPSEEK_API_KEY is not available")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 220,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            return LLMResult("", False, _sanitize_error(f"HTTP {exc.code}: {detail}"))
        except Exception as exc:  # noqa: BLE001 - keep fallback robust for classroom demos.
            return LLMResult("", False, _sanitize_error(str(exc)))

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return LLMResult("", False, _sanitize_error(f"Unexpected response: {data!r}"))

        return LLMResult(str(content).strip(), True, None)


def load_api_key() -> str | None:
    env_key = os.environ.get("DEEPSEEK_API_KEY")
    if env_key:
        return env_key.strip()

    local_key_path = Path(__file__).resolve().parents[1] / "qmh_API.md"
    if not local_key_path.exists():
        return None

    text = local_key_path.read_text(encoding="utf-8").strip()
    match = SECRET_PATTERN.search(text)
    if match:
        return match.group(0)
    return text or None


def _sanitize_error(text: str) -> str:
    return SECRET_PATTERN.sub("sk-***", text)
