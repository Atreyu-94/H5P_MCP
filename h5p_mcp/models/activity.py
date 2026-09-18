"""Native H5P authoring contract; library versions are never guessed."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Activity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1, max_length=200)
    library: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]* [0-9]+\.[0-9]+$")
    params: dict[str, Any]
    language: str = Field(default="en", min_length=2, max_length=20)
    license: str = "U"
    assets: dict[str, str] = Field(default_factory=dict, description="Map asset IDs to absolute local file paths. Reference with asset:<id> in native media path fields.")
