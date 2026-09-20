"""Shell completion for `get <ref>` arguments.

Every completer has the same shape — take what was typed, return the
refs that start with it — so the filtering lives here and each command
supplies only where its candidates come from.
"""

from collections.abc import Callable, Iterable

Candidate = tuple[str, str]  # (ref, one-line label shown beside it)


def completer(candidates: Callable[[], Iterable[Candidate]]) -> Callable[[str], list[Candidate]]:
    """Wrap a candidate source into a Typer ``autocompletion`` callback."""

    def complete(incomplete: str) -> list[Candidate]:
        return [(ref, label) for ref, label in candidates() if ref.startswith(incomplete)]

    return complete
