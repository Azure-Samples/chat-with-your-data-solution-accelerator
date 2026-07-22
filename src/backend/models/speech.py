"""Speech-config response model."""

from pydantic import BaseModel, Field


class SpeechConfig(BaseModel):
    """Browser-consumable Speech-SDK bootstrap payload."""

    token: str = Field(description="10-minute Azure Speech authorization token.")
    region: str = Field(description="Azure region of the Speech account.")
    languages: list[str] = Field(
        description=(
            "BCP-47 language tags the recognizer should auto-detect. "
            "Defaults to v1's `en-US,fr-FR,de-DE,it-IT`."
        )
    )


__all__ = ["SpeechConfig"]
