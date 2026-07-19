import json
import time
from typing import Any, Sequence, TypeVar

from openai import OpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

from inference.contract import Inference
from inference.models import (
    InferenceConfig,
    InferenceResult,
    Message,
    Usage,
)

T = TypeVar("T", bound=BaseModel)


class OpenAIInference(Inference):
    def __init__(self, config: InferenceConfig):
        self._config = config
        self._client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout,
            max_retries=config.max_retries,
        )

    @classmethod
    def from_service(
        cls,
        service_cfg: dict[str, Any],
    ) -> "OpenAIInference":
        return cls(
            InferenceConfig(
                base_url=service_cfg["base_url"],
                api_key=service_cfg.get("api_key", ""),
                model=service_cfg.get("model", ""),
                timeout=service_cfg.get("timeout", 300.0),
                max_retries=service_cfg.get("max_retries", 3),
                retry_on_rate_limit=service_cfg.get("retry_on_rate_limit", False),
            )
        )

    def generate(
        self,
        *,
        messages: Sequence[Message],
        response_model: type[T],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **options: Any,
    ) -> InferenceResult[T]:
        sdk_messages = [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]

        def close_objects(schema: dict) -> dict:
            if isinstance(schema, dict):
                if schema.get("type") == "object":
                    schema.setdefault("additionalProperties", False)
                for value in schema.values():
                    close_objects(value)
            elif isinstance(schema, list):
                for item in schema:
                    close_objects(item)
            return schema

        schema = close_objects(response_model.model_json_schema())
        request: dict[str, Any] = {
            "model": self._config.model,
            "messages": sdk_messages,
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": schema,
                },
            },
            **options,
        }

        if max_tokens is not None:
            request["max_tokens"] = max_tokens

        start = time.perf_counter()
        attempt = 0  # Initialize the retry counter for tracking exponential backoff

        while True:
            try:
                response = self._client.chat.completions.create(**request)
                latency_ms = (time.perf_counter() - start) * 1000.0

                choice = response.choices[0]
                message = choice.message
                content = message.content or ""

                # Stage 1 : JSON decoding
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    print("=" * 80)
                    print("MODEL RETURNED INVALID JSON")
                    print("=" * 80)
                    print(f"Provider : {self._config.base_url}")
                    print(f"Model    : {self._config.model}")
                    print("-" * 80)
                    print(content)
                    print("=" * 80)
                    raise

                # Stage 2 : Contract validation
                try:
                    value = response_model.model_validate(parsed)
                except ValidationError as e:
                    print("=" * 80)
                    print("INFERENCE CONTRACT VIOLATION")
                    print("=" * 80)
                    print(f"Provider : {self._config.base_url}")
                    print(f"Model    : {self._config.model}")
                    print(f"Contract : {response_model.__name__}")
                    print("-" * 80)
                    print("Validation errors:")

                    for error in e.errors():
                        location = ".".join(str(x) for x in error["loc"])
                        print(f"  • {location}: {error['msg']}")

                    print("-" * 80)
                    print("Returned JSON:")
                    print(json.dumps(parsed, indent=2, ensure_ascii=False))
                    print("=" * 80)
                    raise

                usage = None
                if response.usage is not None:
                    usage = Usage(
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens,
                    )

                return InferenceResult(
                    value=value,
                    finish_reason=choice.finish_reason,
                    reasoning=(
                        getattr(message, "reasoning_content", None)
                        or getattr(message, "reasoning", None)
                    ),
                    usage=usage,
                    latency_ms=latency_ms,
                    raw=response.model_dump(),
                )

            except RateLimitError as e:
                if self._config.retry_on_rate_limit:
                    if attempt == 1:
                        print(dict(e.response.headers))
                        print(e.response.text)
                    attempt += 1
                    retry_after_header = e.response.headers.get("retry-after")

                    try:
                        if retry_after_header:
                            sleep_seconds = float(retry_after_header)
                        else:
                            # Exponential Backoff Strategy: 2, 4, 8, 16...
                            # capped at 2480 seconds
                            base_delay = 2.0
                            max_delay = 2480.0
                            sleep_seconds = min(
                                base_delay * (2 ** (attempt - 1)),
                                max_delay,
                            )
                    except ValueError:
                        # Fallback if header contains an unparseable HTTP-date string
                        base_delay = 2.0
                        max_delay = 2480.0
                        sleep_seconds = min(
                            base_delay * (2 ** (attempt - 1)),
                            max_delay,
                        )

                    print("=" * 80)
                    print(
                        f"RATE LIMIT (429) DETECTED (Attempt {attempt}). "
                        f"Retrying after {sleep_seconds:.2f} seconds..."
                    )
                    print(f"Provider : {self._config.base_url}")
                    print(f"Model    : {self._config.model}")
                    print("=" * 80)

                    time.sleep(sleep_seconds)
                    continue
                else:
                    self._log_and_raise_failure()

            except Exception:
                self._log_and_raise_failure()

    def _log_and_raise_failure(self) -> None:
        print("=" * 80)
        print("INFERENCE REQUEST FAILED")
        print("=" * 80)
        print(f"Provider : {self._config.base_url}")
        print(f"Model    : {self._config.model}")
        print("=" * 80)
        raise
