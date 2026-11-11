"""Render document titles from a user-defined template.

Templates contain literal text and plain ``{placeholder}`` tokens from a fixed
whitelist. Missing values render as an empty string. Python format specs,
attribute access, indexing and stray braces are deliberately unsupported.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable, Mapping

BUILTIN_PLACEHOLDERS: dict[str, str] = {
    "document_id": "Paperless-Dokument-ID",
    "title": "Bisheriger Dokumenttitel",
    "original_filename": "Ursprünglicher Dateiname",
    "filename_stem": "Dateiname ohne Erweiterung",
    "file_extension": "Dateierweiterung",
    "mime_type": "MIME-Typ",
    "created_date": "Dokumentdatum (JJJJ-MM-TT)",
    "created_year": "Jahr des Dokumentdatums",
    "created_month": "Monat des Dokumentdatums",
    "created_day": "Tag des Dokumentdatums",
    "correspondent": "Korrespondent",
    "correspondent_id": "Paperless-Korrespondenten-ID",
    "document_type": "Dokumenttyp",
    "document_type_id": "Paperless-Dokumenttyp-ID",
    "tag_ids": "Paperless-Tag-IDs, kommagetrennt",
}
ALLOWED_PLACEHOLDERS: frozenset[str] = frozenset(BUILTIN_PLACEHOLDERS)

_PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
_ADJACENT_SEPARATORS = re.compile(r"([,;/\-])(?:\s*[,;/\-])+")
_EDGE_SEPARATORS = " ,;/-"
MAX_TEMPLATE_LENGTH = 512
MAX_TITLE_LENGTH = 128
_MAX_VALUE_LENGTH = 1024


class InvalidTemplateError(ValueError):
    """Raised when a title template is malformed or unsafe."""


class UnknownPlaceholderError(InvalidTemplateError):
    """Raised when a template references a placeholder outside the whitelist."""

    def __init__(self, name: str, allowed: Collection[str] = ALLOWED_PLACEHOLDERS) -> None:
        super().__init__(
            f"Unbekannter Platzhalter '{{{name}}}'. Erlaubt sind: {', '.join(sorted(allowed))}"
        )
        self.name = name


def placeholder_names(extra: Iterable[str] = ()) -> frozenset[str]:
    """Return built-in and explicitly configured placeholder names."""

    return ALLOWED_PLACEHOLDERS.union(extra)


def validate_template(
    template: str,
    allowed: Collection[str] = ALLOWED_PLACEHOLDERS,
) -> None:
    """Validate length, braces and the placeholder whitelist."""

    if len(template) > MAX_TEMPLATE_LENGTH:
        raise InvalidTemplateError(f"Vorlage ist zu lang (maximal {MAX_TEMPLATE_LENGTH} Zeichen)")
    for match in _PLACEHOLDER_PATTERN.finditer(template):
        name = match.group(1)
        if name not in allowed:
            raise UnknownPlaceholderError(name, allowed)
    remainder = _PLACEHOLDER_PATTERN.sub("", template)
    if "{" in remainder or "}" in remainder:
        raise InvalidTemplateError(
            "Ungültige Vorlage: geschweifte Klammern sind nur für Platzhalter "
            "wie {invoice_number} erlaubt; Formatangaben, Attribute oder "
            "Indizes werden nicht unterstützt"
        )


def render_title(template: str, context: Mapping[str, object]) -> str:
    """Render *template* with *context*, tolerating missing placeholders."""

    validate_template(template, placeholder_names(context))

    def substitute(match: re.Match[str]) -> str:
        value = context.get(match.group(1))
        if value is None:
            return ""
        return str(value)[:_MAX_VALUE_LENGTH]

    rendered = _PLACEHOLDER_PATTERN.sub(substitute, template)
    return _cleanup(rendered)[:MAX_TITLE_LENGTH].rstrip(_EDGE_SEPARATORS).rstrip()


def _cleanup(value: str) -> str:
    """Collapse adjacent separators and trim edges."""

    previous = None
    current = value
    while previous != current:
        previous = current
        current = _ADJACENT_SEPARATORS.sub(r"\1", current)
    current = re.sub(r"\s+", " ", current)
    return current.strip(_EDGE_SEPARATORS).strip()
