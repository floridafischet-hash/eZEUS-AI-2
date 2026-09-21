import pytest

from core.paperless.title_template import (
    MAX_TEMPLATE_LENGTH,
    MAX_TITLE_LENGTH,
    InvalidTemplateError,
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


@pytest.mark.parametrize(
    "template",
    [
        "{title:>999999999}",
        "{invoice_number!r}",
        "{title.__class__}",
        "{title[0]}",
        "{}",
        "{0}",
        "{{invoice_number}}",
        "Rechnung {invoice_number",
        "Rechnung invoice_number}",
        "{ invoice_number }",
    ],
)
def test_rejects_format_semantics_and_stray_braces(template: str) -> None:
    with pytest.raises(InvalidTemplateError):
        validate_template(template)
    with pytest.raises(InvalidTemplateError):
        render_title(template, _ctx(title="X", invoice_number="1"))


def test_unknown_placeholder_is_an_invalid_template() -> None:
    assert issubclass(UnknownPlaceholderError, InvalidTemplateError)


def test_template_and_rendered_title_lengths_are_limited() -> None:
    validate_template("x" * MAX_TEMPLATE_LENGTH)
    with pytest.raises(InvalidTemplateError):
        validate_template("x" * (MAX_TEMPLATE_LENGTH + 1))
    assert render_title("{title}", _ctx(title="A" * 10_000)) == "A" * MAX_TITLE_LENGTH


def test_values_are_literal_and_unicode_is_preserved() -> None:
    context = _ctx(
        correspondent="Müller GmbH – {title.__class__}",
        invoice_number="RE-2026-äöü",
    )
    assert render_title("{correspondent} {invoice_number}", context) == (
        "Müller GmbH – {title.__class__} RE-2026-äöü"
    )


def test_non_string_values_are_rendered() -> None:
    assert render_title("{created_year}", {"created_year": 2026}) == "2026"
