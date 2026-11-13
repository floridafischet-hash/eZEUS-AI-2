import pytest

from connectors.base.interface import ConnectorDocument
from core.orchestration.orchestrator import Orchestrator
from core.paperless.title_template import (
    ALLOWED_PLACEHOLDERS,
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
        "delivery_note_number": "",
        "correspondent": "",
        "document_type": "",
        "created_date": "",
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


def test_complete_builtin_placeholder_list_is_available() -> None:
    assert {
        "document_id",
        "title",
        "original_filename",
        "filename_stem",
        "file_extension",
        "mime_type",
        "created_date",
        "created_year",
        "created_month",
        "created_day",
        "correspondent",
        "correspondent_id",
        "document_type",
        "document_type_id",
        "tag_ids",
    } == ALLOWED_PLACEHOLDERS


def test_configured_field_is_accepted_from_runtime_context() -> None:
    assert render_title("{cost_center} - {title}", {"cost_center": "4711"}) == "4711"


def test_empty_configured_field_collapses_separators() -> None:
    context = {"document_type": "Rechnung", "cost_center": "", "invoice_number": "RE-42"}
    assert (
        render_title("{document_type} - {cost_center} - {invoice_number}", context)
        == "Rechnung - RE-42"
    )


def test_missing_middle_placeholder_collapses_separators() -> None:
    template = "{document_type}, {invoice_number}, {correspondent}"
    ctx = _ctx(document_type="Rechnung", correspondent="Müller GmbH")
    assert render_title(template, ctx) == "Rechnung, Müller GmbH"


def test_delivery_note_title_uses_document_type_and_delivery_note_number() -> None:
    template = "{document_type}, {invoice_number}, {delivery_note_number}"
    ctx = _ctx(document_type="Lieferschein", delivery_note_number="LI-2026-0042")

    assert render_title(template, ctx) == "Lieferschein, LI-2026-0042"


def test_missing_edges_are_trimmed() -> None:
    template = "{correspondent} - {document_type}"
    ctx = _ctx(document_type="Rechnung")
    assert render_title(template, ctx) == "Rechnung"


def test_slash_separator_collapses() -> None:
    template = "{created_year}/{document_type}/{invoice_number}"
    ctx = _ctx(created_year="2026", invoice_number="RE-123")
    assert render_title(template, ctx) == "2026/RE-123"


def test_created_date_placeholder_renders_complete_date() -> None:
    assert (
        render_title(
            "{created_date} - {document_type}",
            _ctx(created_date="2026-11-11", document_type="Rechnung"),
        )
        == "2026-11-11 - Rechnung"
    )


@pytest.mark.asyncio
async def test_title_context_exposes_complete_created_date() -> None:
    orchestrator = object.__new__(Orchestrator)
    document = ConnectorDocument(
        external_id="1",
        created="2026-11-11T14:30:00+00:00",
    )

    context = await orchestrator._build_title_context(object(), document, {})

    assert context["created_date"] == "2026-11-11"


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


@pytest.mark.asyncio
async def test_orchestrator_title_context_includes_delivery_note_number() -> None:
    class Connector:
        async def get_document_type_name(self, _document_type_id: str) -> str:
            return "Lieferschein"

    document = ConnectorDocument(external_id="1", document_type_id="7")
    orchestrator = Orchestrator.__new__(Orchestrator)

    context = await orchestrator._build_title_context(
        Connector(),  # type: ignore[arg-type]
        document,
        {"delivery_note_number": "LI-2026-0042"},
    )

    assert context["document_type"] == "Lieferschein"
    assert context["delivery_note_number"] == "LI-2026-0042"


@pytest.mark.asyncio
async def test_orchestrator_title_context_contains_all_document_metadata() -> None:
    document = ConnectorDocument(
        external_id="42",
        title="Alter Titel",
        filename="rechnung.final.pdf",
        mime_type="application/pdf",
        document_type_id="7",
        correspondent_id="8",
        tag_ids=frozenset({"10", "2"}),
        created="2026-11-11T12:34:56+00:00",
    )
    orchestrator = Orchestrator.__new__(Orchestrator)

    context = await orchestrator._build_title_context(  # type: ignore[arg-type]
        object(), document, {"cost_center": "4711"}
    )

    assert context == {
        "cost_center": "4711",
        "document_id": "42",
        "title": "Alter Titel",
        "original_filename": "rechnung.final.pdf",
        "filename_stem": "rechnung.final",
        "file_extension": "pdf",
        "mime_type": "application/pdf",
        "created_date": "2026-11-11",
        "created_year": "2026",
        "created_month": "11",
        "created_day": "11",
        "correspondent": "",
        "correspondent_id": "8",
        "document_type": "",
        "document_type_id": "7",
        "tag_ids": "2, 10",
    }
