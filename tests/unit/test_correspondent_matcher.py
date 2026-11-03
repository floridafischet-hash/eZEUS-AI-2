from connectors.base.interface import ConnectorCorrespondent
from core.correspondents.matcher import (
    DEFAULT_CORRESPONDENT_NAME,
    default_correspondent,
    match_correspondent,
)


def _correspondent(
    external_id: str,
    name: str,
    match: str = "",
    matching_algorithm: int = 0,
) -> ConnectorCorrespondent:
    return ConnectorCorrespondent(
        external_id=external_id,
        name=name,
        match=match,
        matching_algorithm=matching_algorithm,
        is_insensitive=True,
    )


def test_exact_supplier_name_is_selected() -> None:
    result = match_correspondent(
        "PS Hydraulik GmbH\nClean Power AG\nRECHNUNG",
        [
            _correspondent("1", "PS Hydraulik GmbH"),
            _correspondent("2", "Clean Power AG"),
        ],
    )

    assert result is not None
    assert result.correspondent_id == "1"
    assert result.score == 1.0


def test_match_below_sixty_percent_is_rejected() -> None:
    result = match_correspondent(
        "Completely unrelated document",
        [_correspondent("1", "PS Hydraulik GmbH")],
    )

    assert result is None


def test_single_word_name_requires_a_complete_match() -> None:
    result = match_correspondent(
        "Blumen und Wunder der Natur",
        [_correspondent("1", "Blumenwunder")],
    )

    assert result is None


def test_more_specific_name_wins_on_same_line() -> None:
    result = match_correspondent(
        "H. Busse GmbH & Co. KG",
        [
            _correspondent("1", "Busse GmbH & Co. KG"),
            _correspondent("2", "H. Busse GmbH & Co. KG"),
        ],
    )

    assert result is not None
    assert result.correspondent_id == "2"


def test_equal_matches_remain_unassigned() -> None:
    result = match_correspondent(
        "Example GmbH",
        [
            _correspondent("1", "Example GmbH"),
            _correspondent("2", "Example GmbH"),
        ],
    )

    assert result is None


def test_explicit_any_word_rule_below_threshold_is_rejected() -> None:
    result = match_correspondent(
        "Invoice issued by Alpha",
        [_correspondent("1", "Unrelated Name", "Alpha Service Nord", 1)],
    )

    assert result is None


def test_explicit_any_word_rule_accepts_sixty_percent_boundary() -> None:
    result = match_correspondent(
        "Invoice issued by Alpha Service Nord",
        [_correspondent("1", "Unrelated Name", "Alpha Service Nord West Süd", 1)],
    )

    assert result is not None
    assert result.correspondent_id == "1"
    assert result.score == 0.6


def test_correspondent_name_is_checked_when_explicit_rule_does_not_match() -> None:
    result = match_correspondent(
        "Invoice issued by Alpha Service GmbH",
        [_correspondent("1", "Alpha Service GmbH", "missing.example", 3)],
    )

    assert result is not None
    assert result.correspondent_id == "1"
    assert result.score == 1.0
    assert result.source == "correspondent_name"


def test_stronger_name_match_wins_over_explicit_rule_for_same_correspondent() -> None:
    result = match_correspondent(
        "Alpha Service GmbH\nContact: service@example.invalid",
        [_correspondent("1", "Alpha Service GmbH", "service example missing", 1)],
    )

    assert result is not None
    assert result.correspondent_id == "1"
    assert result.score == 1.0
    assert result.source == "correspondent_name"


def test_default_correspondent_is_only_used_as_explicit_fallback() -> None:
    fallback = _correspondent("99", DEFAULT_CORRESPONDENT_NAME)

    assert default_correspondent([fallback]) == fallback
    assert match_correspondent("Status: noch nicht angelegt", [fallback]) is None


def test_default_correspondent_without_parentheses_is_supported() -> None:
    fallback = _correspondent("99", "noch nicht angelegt")

    assert default_correspondent([fallback]) == fallback
    assert match_correspondent("Status: (noch nicht angelegt)", [fallback]) is None


def test_exact_name_split_across_ocr_lines_is_prioritized() -> None:
    result = match_correspondent(
        "Ernst Hasselbring\nGmbH & Co. KG\nRECHNUNG",
        [
            _correspondent("1", "Famo GmbH & Co.KG"),
            _correspondent("2", "Ernst Hasselbring GmbH & Co. KG"),
        ],
    )

    assert result is not None
    assert result.correspondent_id == "2"
    assert result.score == 1.0


def test_implicit_name_match_requires_eighty_five_percent() -> None:
    result = match_correspondent(
        "Gebr. Meyer · Alter Postweg 8-10 · 21614 Buxtehude",
        [_correspondent("1", "Gebr. Loesing GbR.")],
    )

    assert result is None


def test_implicit_name_match_requires_a_distinctive_company_word() -> None:
    result = match_correspondent(
        "Wümme-Beton GmbH & Co. KG · Industriestr. 5 · 27383 Scheeßel",
        [
            _correspondent("1", "Famo GmbH & Co.KG"),
            _correspondent("2", "OASE GmbH"),
        ],
    )

    assert result is None


def test_exact_existing_supplier_beats_unrelated_fuzzy_candidate() -> None:
    result = match_correspondent(
        "Mibau Stema Deutschland GmbH, Gewerbestraße 3, 21781 Cadenberge",
        [
            _correspondent("1", "Thomas Beton GmbH"),
            _correspondent("2", "Mibau Stema Deutschland GmbH"),
        ],
    )

    assert result is not None
    assert result.correspondent_id == "2"
    assert result.score == 1.0


def test_sender_name_beats_court_mentioned_only_as_register_reference() -> None:
    result = match_correspondent(
        "Example Service GmbH\nMusterweg 12\nRECHNUNG\nRegistergericht: Amtsgericht Beispielstadt",
        [
            _correspondent("1", "Amtsgericht Beispielstadt"),
            _correspondent("2", "Example Service GmbH"),
        ],
    )

    assert result is not None
    assert result.correspondent_id == "2"
    assert result.score == 1.0


def test_name_mentioned_only_as_register_court_is_not_selected() -> None:
    result = match_correspondent(
        "Example Service GmbH\nHandelsregister: Amtsgericht Beispielstadt HRB 12345",
        [_correspondent("1", "Amtsgericht Beispielstadt")],
    )

    assert result is None


def test_actual_court_sender_is_selected_despite_later_register_reference() -> None:
    result = match_correspondent(
        "Amtsgericht Beispielstadt\nGerichtsstraße 1\nBESCHLUSS\n"
        "Registergericht: Amtsgericht Beispielstadt",
        [_correspondent("1", "Amtsgericht Beispielstadt")],
    )

    assert result is not None
    assert result.correspondent_id == "1"


def test_sender_context_wins_when_two_exact_names_are_present() -> None:
    result = match_correspondent(
        "Empfänger AG\nAbsender: Example Service GmbH\nRECHNUNG",
        [
            _correspondent("1", "Empfänger AG"),
            _correspondent("2", "Example Service GmbH"),
        ],
    )

    assert result is not None
    assert result.correspondent_id == "2"


def test_reference_marker_on_adjacent_line_rejects_court_name() -> None:
    result = match_correspondent(
        "Example Service GmbH\nMusterweg 12\nGeschäftsführer: Erika Beispiel\n"
        "HRB 12345\nAmtsgericht Beispielstadt",
        [
            _correspondent("1", "Amtsgericht Beispielstadt"),
            _correspondent("2", "Example Service GmbH"),
        ],
    )

    assert result is not None
    assert result.correspondent_id == "2"


def test_reference_only_name_with_adjacent_vat_marker_is_rejected() -> None:
    result = match_correspondent(
        "USt-ID: DE123456789\nAmtsgericht Beispielstadt",
        [_correspondent("1", "Amtsgericht Beispielstadt")],
    )

    assert result is None


def test_company_in_legal_footer_beats_referenced_court() -> None:
    result = match_correspondent(
        "Example Handel KG\nUSt-ID: DE123456789\nHRB 12345\nAmtsgericht Beispielstadt",
        [
            _correspondent("1", "70247 Example Handel KG"),
            _correspondent("2", "Amtsgericht Beispielstadt"),
        ],
    )

    assert result is not None
    assert result.correspondent_id == "1"


def test_internal_numeric_suffix_is_ignored_for_company_name_match() -> None:
    result = match_correspondent(
        "Example Parts GmbH\nMusterweg 12\nRECHNUNG",
        [_correspondent("1", "Example Parts GmbH 70364")],
    )

    assert result is not None
    assert result.correspondent_id == "1"
    assert result.name == "Example Parts GmbH 70364"


def test_internal_numeric_prefix_is_ignored_for_company_name_match() -> None:
    result = match_correspondent(
        "Example Handel KG\nMusterweg 12\nRECHNUNG",
        [_correspondent("1", "70247 Example Handel KG")],
    )

    assert result is not None
    assert result.correspondent_id == "1"
    assert result.name == "70247 Example Handel KG"


def test_legitimate_number_without_company_form_is_not_removed() -> None:
    result = match_correspondent(
        "Studio Example\nMusterweg 12",
        [_correspondent("1", "Studio Example 2024")],
    )

    assert result is None


def test_explicit_matching_rule_keeps_numeric_tokens() -> None:
    result = match_correspondent(
        "Kundencode 70364",
        [_correspondent("1", "Example Parts GmbH 70364", "Kundencode 70364", 3)],
    )

    assert result is not None
    assert result.correspondent_id == "1"
    assert result.source == "matching_rule"
