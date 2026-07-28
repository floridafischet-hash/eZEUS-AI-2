from connectors.base.interface import ConnectorCorrespondent
from core.correspondents.matcher import match_correspondent


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


def test_explicit_any_word_rule_uses_match_ratio() -> None:
    result = match_correspondent(
        "Invoice issued by Alpha Service",
        [_correspondent("1", "Unrelated Name", "Alpha Service Nord", 1)],
    )

    assert result is not None
    assert result.correspondent_id == "1"
    assert result.score == 2 / 3
