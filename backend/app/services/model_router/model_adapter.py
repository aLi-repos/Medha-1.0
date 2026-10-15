"""Model adapters — real local open-weight LLM runtime + external proxy stub.

LocalSmallLLMAdapter performs REAL inference by calling a locally running,
Ollama-compatible open-weight model server configured via
MEDHA_LOCAL_LLM_BASE_URL / MEDHA_LOCAL_LLM_MODEL / MEDHA_LOCAL_LLM_TIMEOUT.
It never calls a cloud LLM API. If the local runtime is unreachable the
adapter raises LocalModelUnavailableError so callers can FAIL CLOSED —
there is no echo/simulated fallback for the local path and no silent cloud
fallback.

APIProxyAdapter remains a clearly-labeled simulated external proxy used
only for routing/policy demonstrations; it is never the sovereign path.
"""

from __future__ import annotations

import json
import time
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.config import settings

LOCAL_RUNTIME_NAME = "ollama-compatible"
UNAVAILABLE_MESSAGE = (
    "Local AI model is unavailable. Start the configured local inference runtime."
)


class LocalModelUnavailableError(RuntimeError):
    """Raised when the configured local inference runtime cannot serve."""


def _http_post(url: str, payload: dict, timeout: int) -> dict:
    """HTTP POST transport (mockable seam for tests)."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_get(url: str, timeout: int) -> dict:
    """HTTP GET transport (mockable seam for tests)."""
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class LocalLLMClient:
    """Client for a local open-weight inference server (Ollama-compatible)."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (
            base_url if base_url is not None else settings.local_llm_base_url
        ).rstrip("/")
        self.model = model if model is not None else settings.local_llm_model
        self.timeout = timeout if timeout is not None else settings.local_llm_timeout

    def complete(self, prompt: str, max_tokens: int = 512) -> tuple[str, int, float]:
        """Run local generation. Raises LocalModelUnavailableError on failure."""
        started = time.perf_counter()
        try:
            data = _http_post(
                f"{self.base_url}/api/generate",
                {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
                self.timeout,
            )
        except Exception as exc:
            raise LocalModelUnavailableError(
                f"{UNAVAILABLE_MESSAGE} ({type(exc).__name__})"
            ) from exc

        text = str((data or {}).get("response") or "")
        if not text.strip():
            raise LocalModelUnavailableError(
                f"{UNAVAILABLE_MESSAGE} (empty response from runtime)"
            )

        elapsed_ms = (time.perf_counter() - started) * 1000
        eval_count = (data or {}).get("eval_count")
        try:
            tokens = int(eval_count)
        except (TypeError, ValueError):
            tokens = len(prompt.split()) + len(text.split())
        return text, max(1, tokens), elapsed_ms

    def health(self) -> dict[str, str]:
        """Runtime/model health without exposing configuration internals."""
        try:
            data = _http_get(f"{self.base_url}/api/tags", self.timeout)
        except Exception as exc:
            return {
                "runtime": LOCAL_RUNTIME_NAME,
                "model": self.model,
                "status": "UNAVAILABLE",
                "reason": f"local inference runtime unreachable ({type(exc).__name__})",
            }

        names = [
            str(m.get("name", ""))
            for m in ((data or {}).get("models") or [])
            if isinstance(m, dict)
        ]
        if self._model_installed(names):
            return {
                "runtime": LOCAL_RUNTIME_NAME,
                "model": self.model,
                "status": "AVAILABLE",
                "reason": "configured model installed on local runtime",
            }
        return {
            "runtime": LOCAL_RUNTIME_NAME,
            "model": self.model,
            "status": "UNAVAILABLE",
            "reason": "configured model not installed on local runtime",
        }

    def _model_installed(self, names: list[str]) -> bool:
        if self.model in names:
            return True
        if ":" not in self.model:
            return any(n == self.model or n.startswith(f"{self.model}:") for n in names)
        return False


@dataclass
class ModelResponse:
    model_name: str
    text: str
    tokens_used: int
    latency_ms: float


class ModelAdapter(ABC):
    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 512) -> ModelResponse:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class LocalSmallLLMAdapter(ModelAdapter):
    """Real local open-weight LLM adapter (e.g. Qwen-2 via local runtime)."""

    def __init__(self, client: LocalLLMClient | None = None) -> None:
        self._client = client or LocalLLMClient()

    @property
    def name(self) -> str:
        return "local-qwen2"

    def generate(self, prompt: str, max_tokens: int = 512) -> ModelResponse:
        text, tokens, latency_ms = self._client.complete(prompt, max_tokens)
        return ModelResponse(
            model_name=self.name,
            text=text,
            tokens_used=tokens,
            latency_ms=round(latency_ms, 2),
        )

    def health(self) -> dict[str, str]:
        return self._client.health()


class APIProxyAdapter(ModelAdapter):
    """Simulated API proxy to OpenAI/Claude — never a sovereign-path adapter.

    Kept for routing/policy demonstrations only; does not perform real
    external inference. External models are blocked by security mode,
    network policy and allowed-model checks before reaching this adapter.
    """

    def __init__(self, provider: str = "openai") -> None:
        self._provider = provider

    @property
    def name(self) -> str:
        return f"api-{self._provider}"

    def generate(self, prompt: str, max_tokens: int = 512) -> ModelResponse:
        response_text = (
            f"[{self._provider.title()} API Response] Complex analysis completed "
            f"for the query: {prompt[:100]}"
        )
        return ModelResponse(
            model_name=self.name,
            text=response_text,
            tokens_used=len(prompt.split()) + 100,
            latency_ms=250.0,
        )


class ModelAdapterFactory:
    _adapters: dict[str, ModelAdapter] = {}

    @classmethod
    def register(cls, name: str, adapter: ModelAdapter) -> None:
        cls._adapters[name] = adapter

    @classmethod
    def get(cls, name: str) -> ModelAdapter:
        if name not in cls._adapters:
            raise ValueError(f"Unknown model adapter: {name}")
        return cls._adapters[name]

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._adapters.keys())


def _init_defaults() -> None:
    if not ModelAdapterFactory._adapters:
        ModelAdapterFactory.register("local-qwen2", LocalSmallLLMAdapter())
        ModelAdapterFactory.register("api-openai", APIProxyAdapter("openai"))
        ModelAdapterFactory.register("api-claude", APIProxyAdapter("claude"))


_init_defaults()
