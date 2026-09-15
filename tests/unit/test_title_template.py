import pytest

from core.paperless.title_template import (
    UnknownPlaceholderError,
    render_title,
    validate_template,
)


def _ctx(**overrides: str) -> dict[str, str]:
    base = {
        "invoice_number": "",
        "correspondent": "",
        "document_type": "",
        "created_year": "",
        "created_month": "",
        "created_day": "",
        "original_filename": "",
        "title": "",
    }
    base.update(overrides)
    return base


def test_all_placeholders_present() -> None:
    template = "{document_type}, {invoice_number}, {correspondent}"
    ctx = _ctx(
        document_type="Rechnung",
        invoice_number="RE-2026-00123",
        correspondent="Müller GmbH",
    )
    assert render_title(template, ctx) == "Rechnung, RE-2026-00123, Müller GmbH"


def test_missing_middle_placeholder_collapses_separators() -> None:
    template = "{document_type}, {invoice_number}, {correspondent}"
    ctx = _ctx(document_type="Rechnung", correspondent="Müller GmbH")
    assert render_title(template, ctx) == "Rechnung, Müller GmbH"


def test_missing_edges_are_trimmed() -> None:
    template = "{correspondent} - {document_type}"
    ctx = _ctx(document_type="Rechnung")
    assert render_title(template, ctx) == "Rechnung"


def test_slash_separator_collapses() -> None:
    template = "{created_year}/{document_type}/{invoice_number}"
    ctx = _ctx(created_year="2026", invoice_number="RE-123")
    assert render_title(template, ctx) == "2026/RE-123"


def test_dashes_in_values_are_preserved() -> None:
    template = "{invoice_number} - {correspondent}"
    ctx = _ctx(invoice_number="RE-2026-00123", correspondent="Müller")
    assert render_title(template, ctx) == "RE-2026-00123 - Müller"


def test_unknown_placeholder_raises() -> None:
    with pytest.raises(UnknownPlaceholderError) as exc:
        validate_template("{foo}, {invoice_number}")
    assert exc.value.name == "foo"


def test_render_rejects_unknown_placeholder() -> None:
    with pytest.raises(UnknownPlaceholderError):
        render_title("{foo}", _ctx())


def test_empty_template_yields_empty_string() -> None:
    assert render_title("", _ctx(invoice_number="X")) == ""


def test_only_missing_values_returns_empty_string() -> None:
    template = "{document_type}, {invoice_number}, {correspondent}"
    assert render_title(template, _ctx()) == ""


def test_repeated_placeholder_works() -> None:
    template = "{correspondent}-{correspondent}"
    ctx = _ctx(correspondent="Foo")
    assert render_title(template, ctx) == "Foo-Foo"
