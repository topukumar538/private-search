from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SearchResult(BaseModel):
    """One result returned by a search source, before merging and ranking."""

    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)

    title: str = Field(min_length=1)
    url: str
    snippet: str = ""
    source: str = Field(min_length=1)

    @field_validator("url")
    @classmethod
    def must_be_web_url(cls, value: str) -> str:
        parts = urlsplit(value)

        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise ValueError("URL must be an http or https web address.")

        return value