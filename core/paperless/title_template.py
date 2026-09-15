"""Render document titles from a user-defined template.

Templates use Python ``str.format`` placeholders limited to a whitelist.
Missing values render as an empty string rather than raising ``KeyError``,
and separator characters left behind by empty placeholders (``,`` ``;``
``/`` ``-``) are collapsed so the rendered title does not contain visible
artefacts like ``"Rechnung, , Müller"``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

ALLOWED_PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "invoice_number",
        "correspondent",
        "document_type",
        "created_year",
        "created_month",
        "created_day",
        "original_filename",
        "title",
    }
)

_PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
_ADJACENT_SEPARATORS = re.compile(r"([,;/\-])(?:\s*[,;/\-])+")
_EDGE_SEPARATORS = " ,;/-"


class UnknownPlaceholderError(ValueError):
    """Raised when a template references a placeholder outside the whitelist."""

    def __init__(self, name: str) -> None:
        super().__init__(
            f"Unbekannter Platzhalter '{{{name}}}'. "
            f"Erlaubt sind: {', '.join(sorted(ALLOWED_PLACEHOLDERS))}"
        )
        self.name = name


def validate_template(template: str) -> None:
    """Raise ``UnknownPlaceholderError`` for any non-whitelisted placeholder."""

    for match in _PLACEHOLDER_PATTERN.finditer(template):
        name = match.group(1)
        if name not in ALLOWED_PLACEHOLDERS:
            raise UnknownPlaceholderError(name)


def render_title(template: str, context: Mapping[str, object]) -> str:
    """Render *template* with *context*, tolerating missing placeholders."""

    validate_template(template)
    safe: dict[str, str] = {
        key: str(context.get(key, "") or "") for key in ALLOWED_PLACEHOLDERS
    }
    rendered = template.format_map(safe)
    return _cleanup(rendered)


def _cleanup(value: str) -> str:
    """Collapse adjacent separators and trim edges."""

    previous = None
    current = value
    while previous != current:
        previous = current
        current = _ADJACENT_SEPARATORS.sub(r"\1", current)
    current = re.sub(r"\s+", " ", current)
    return current.strip(_EDGE_SEPARATORS).strip()
