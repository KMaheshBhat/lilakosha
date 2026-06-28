from typing import Any, Protocol, Sequence, TypeVar

from pydantic import BaseModel

from inference.models import InferenceResult, Message

T = TypeVar("T", bound=BaseModel)


class Inference(Protocol):
    def generate(
        self,
        *,
        messages: Sequence[Message],
        response_model: type[T],
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **options: Any,
    ) -> InferenceResult[T]: ...
