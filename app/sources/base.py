from abc import ABC, abstractmethod
from collections.abc import Iterable

from pydantic import ValidationError

from app.models import SearchResult


class SearchSource(ABC):
    """The contract every search source must follow."""

    # Short, unique id such as "wikipedia". Shown to users and used in ranking.
    name: str

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        # Catch a missing name when the class is written, not at search time.
        if not getattr(cls, "name", ""):
            raise TypeError(f"{cls.__name__} must define a non-empty 'name'.")

    @abstractmethod
    async def search(self, query: str) -> list[SearchResult]:
        """Return results for the query, best first.

        Raise an exception if the source itself fails (network error,
        bad status, missing API key). The orchestrator treats that as
        "this source is unavailable" and keeps the other sources' results.
        """

    def build_results(self, items: Iterable[dict]) -> list[SearchResult]:
        """Turn raw items into validated results, skipping invalid ones.

        One bad item (missing title, non-web URL) must not cost us the
        rest of this source's results.
        """
        results = []

        for item in items:
            try:
                results.append(SearchResult(**item, source=self.name))
            except (ValidationError, TypeError):
                continue

        return results