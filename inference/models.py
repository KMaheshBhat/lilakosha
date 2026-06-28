from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> "Message":
        return cls(role="assistant", content=content)


class Usage(BaseModel):
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


T = TypeVar("T", bound=BaseModel)


class InferenceResult(BaseModel, Generic[T]):
    value: T
    finish_reason: str | None
    reasoning: str | None
    usage: Usage | None
    latency_ms: float | None
    raw: dict[str, Any] | None


class InferenceConfig(BaseModel):
    base_url: str
    api_key: str
    model: str
    timeout: float = 300.0
    max_retries: int = 3
