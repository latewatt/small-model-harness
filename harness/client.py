"""Minimal OpenAI-compatible transport with measured usage and bounded retries."""
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


class HarnessError(Exception):
    pass


class BudgetExceeded(HarnessError):
    pass


class APIError(HarnessError):
    pass


@dataclass
class ModelConfig:
    model: str
    base_url: str = "http://127.0.0.1:11435/v1"
    max_tokens: int = 1024
    temperature: float = 0.0
    seed: int = 17
    request_timeout: float = 90


class Client:
    def __init__(self, config: ModelConfig, trace, deadline: float):
        self.config, self.trace, self.deadline = config, trace, deadline
        self.calls = self.http_attempts = 0
        self.prompt_tokens = self.completion_tokens = 0
        self.usage_complete = True
        self.api_seconds = 0.0

    def query(self, messages: list[dict], *, response_format: dict | None = None) -> dict:
        self.calls += 1
        # Only standard conversation fields go to the provider; upstream trace
        # metadata and local paths in `extra` are never serialized as messages.
        clean = [{k: v for k, v in m.items() if k in ("role", "content", "tool_calls", "tool_call_id", "name")} for m in messages]
        payload = {"model": self.config.model, "messages": clean,
                   "max_tokens": self.config.max_tokens, "temperature": self.config.temperature,
                   "seed": self.config.seed, "stream": False}
        if response_format is not None:
            payload["response_format"] = response_format
        # Explicitly disable hidden thinking for the controlled local comparison.
        # Generic providers receive only standard compatible fields by default.
        if os.environ.get("HARNESS_REASONING_EFFORT", ""):
            payload["reasoning_effort"] = os.environ["HARNESS_REASONING_EFFORT"]
        elif self.config.base_url.startswith("http://127.0.0.1:11435"):
            payload["reasoning_effort"] = "none"
        self.trace.emit("request", call=self.calls, payload=payload)
        key = os.getenv("HARNESS_API_KEY") or os.getenv("OPENAI_API_KEY") or "local"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
        for attempt in range(2):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise BudgetExceeded("task wall-time budget exhausted")
            self.http_attempts += 1
            started = time.monotonic()
            try:
                req = urllib.request.Request(self.config.base_url.rstrip("/") + "/chat/completions",
                                             data=json.dumps(payload).encode(), headers=headers)
                with urllib.request.urlopen(req, timeout=min(self.config.request_timeout, remaining)) as response:
                    raw = response.read(8 * 1024 * 1024)
                result = json.loads(raw)
                elapsed = time.monotonic() - started
                self.api_seconds += elapsed
                usage = result.get("usage") or {}
                known = all(type(usage.get(k)) is int for k in ("prompt_tokens", "completion_tokens"))
                self.usage_complete &= known
                if known:
                    self.prompt_tokens += usage["prompt_tokens"]
                    self.completion_tokens += usage["completion_tokens"]
                self.trace.emit("response", call=self.calls, response=result, api_s=elapsed, usage_known=known)
                if not result.get("choices"):
                    raise APIError("provider response has no choices")
                return result
            except urllib.error.HTTPError as exc:
                # Do not log provider error bodies: some providers echo auth data.
                self.api_seconds += time.monotonic() - started
                self.usage_complete = False
                self.trace.emit("api_error", call=self.calls, status=exc.code, attempt=attempt + 1)
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 1:
                    raise APIError(f"HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                self.api_seconds += time.monotonic() - started
                # A timed-out request may have consumed unknown tokens. Never
                # represent partial accounting as an exact total.
                self.usage_complete = False
                self.trace.emit("api_error", call=self.calls, error=type(exc).__name__, attempt=attempt + 1)
                raise APIError(type(exc).__name__) from exc
            except (ValueError, KeyError, TypeError) as exc:
                self.usage_complete = False
                raise APIError(f"invalid provider JSON: {type(exc).__name__}") from exc
            pause = min(1.0, max(0.0, self.deadline - time.monotonic()))
            time.sleep(pause)
        raise APIError("retry budget exhausted")

    def stats(self):
        return {"calls": self.calls, "http_attempts": self.http_attempts,
                "prompt_tokens": self.prompt_tokens if self.usage_complete else None,
                "completion_tokens": self.completion_tokens if self.usage_complete else None,
                "observed_prompt_tokens": self.prompt_tokens,
                "observed_completion_tokens": self.completion_tokens,
                "usage_complete": self.usage_complete, "api_s": self.api_seconds}
