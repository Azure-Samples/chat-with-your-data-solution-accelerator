from typing import Any


def build_completion_kwargs(model_name: str | None, max_tokens: int | None, **kwargs: Any) -> dict[str, Any]:
    """Return request kwargs that are compatible with newer Azure OpenAI models."""
    if max_tokens is None:
        return kwargs

    normalized_model = (model_name or "").lower()
    if "gpt-5" in normalized_model or normalized_model.startswith(("o1", "o3", "o4")):
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens

    return kwargs
