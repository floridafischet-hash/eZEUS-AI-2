import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

import regex

from connectors.base.interface import ConnectorCorrespondent
from core.config.settings import get_settings

DEFAULT_CORRESPONDENT_NAME = "(noch nicht angelegt)"
DEFAULT_CORRESPONDENT_NAMES = (DEFAULT_CORRESPONDENT_NAME, "noch nicht angelegt")
MINIMUM_NAME_SCORE = 0.85

_SENDER_CONTEXT_MARKERS = (
    "absender",
    "aussteller",
    "herausgeber",
    "rechnung von",
    "angebot von",
    "mit freundlichen gruessen",
)
_REFERENCE_CONTEXT_MARKERS = (
    "aktenzeichen",
    "eingetragen beim",
    "gerichtsstand",
    "handelsregister",
    "registergericht",
    "rechtsbehelfsbelehrung",
    "zustaendiges gericht",
)

_NON_DISTINCTIVE_COMPANY_WORDS = {
    "ag",
    "beton",
    "co",
    "e",
    "geb",  # OCR abbreviation for Gebrüder
    "gebr",
    "gebrueder",
    "gesellschaft",
    "gbr",
    "gmbh",
    "group",
    "gruppe",
    "holding",
    "kg",
    "kgaa",
    "mbh",
    "ohg",
    "ug",
    "v",
}


@dataclass(slots=True, frozen=True)
class CorrespondentMatch:
    correspondent_id: str
    name: str
    score: float
    source: str
    line_number: int


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return " ".join(
        "".join(character for character in decomposed if character.isalnum() or character.isspace())
        .casefold()
        .split()
    )


def _is_default_correspondent_name(value: str) -> bool:
    normalized_defaults = {_normalize(name) for name in DEFAULT_CORRESPONDENT_NAMES}
    return _normalize(value) in normalized_defaults


def default_correspondent(
    correspondents: list[ConnectorCorrespondent],
) -> ConnectorCorrespondent | None:
    return next(
        (item for item in correspondents if _is_default_correspondent_name(item.name)),
        None,
    )


def _distinctive_words(value: str) -> set[str]:
    return {
        word
        for word in _normalize(value).split()
        if word not in _NON_DISTINCTIVE_COMPANY_WORDS and len(word) > 1
    }


def _line_score(rule: str, line: str, *, require_distinctive_word: bool = False) -> float:
    normalized_rule = _normalize(rule)
    normalized_line = _normalize(line)
    if not normalized_rule or not normalized_line:
        return 0.0
    if normalized_rule in normalized_line:
        return 1.0
    if len(normalized_rule.split()) == 1:
        return 0.0
    if require_distinctive_word and not (_distinctive_words(rule) & set(normalized_line.split())):
        return 0.0
    return SequenceMatcher(None, normalized_rule, normalized_line).ratio()


def _name_context(rule: str, lines: list[str]) -> tuple[int, int]:
    """Return sender-context priority and first exact occurrence for a name.

    A name that occurs only as part of a register, court or case reference must not
    become the correspondent merely because the spelling is exact.  Windows allow
    company names split over adjacent OCR lines to retain their exact-name match.
    """

    normalized_rule = _normalize(rule)
    occurrences: list[tuple[int, int]] = []
    for start in range(len(lines)):
        for width in range(1, min(3, len(lines) - start) + 1):
            window = _normalize(" ".join(lines[start : start + width]))
            if normalized_rule not in window:
                continue
            if any(marker in window for marker in _REFERENCE_CONTEXT_MARKERS):
                priority = 0
            elif any(marker in window for marker in _SENDER_CONTEXT_MARKERS):
                priority = 2
            else:
                priority = 1
            occurrences.append((priority, start))

    if not occurrences:
        return 1, 2**31 - 1
    return min(occurrences, key=lambda item: (-item[0], item[1]))


def _score_rule(correspondent: ConnectorCorrespondent, text: str) -> tuple[float, int, int, str]:
    rule = correspondent.match.strip() or correspondent.name.strip()
    source = "matching_rule" if correspondent.match.strip() else "correspondent_name"
    if not rule:
        return 0.0, 1, 2**31 - 1, source
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    algorithm = correspondent.matching_algorithm
    if algorithm == 4 and correspondent.match.strip():
        flags = regex.IGNORECASE if correspondent.is_insensitive else 0
        try:
            match = regex.search(
                rule,
                text,
                flags,
                timeout=get_settings().regex_hard_timeout_seconds,
            )
        except (regex.error, TimeoutError):
            return 0.0, 1, 2**31 - 1, source
        if match is None:
            return 0.0, 1, 2**31 - 1, source
        line_number = text[: match.start()].count("\n")
        return 1.0, 1, line_number, source

    normalized_text = _normalize(text)
    words = [_normalize(word) for word in regex.split(r"[\s,;|]+", rule) if _normalize(word)]
    if correspondent.match.strip() and algorithm in {1, 2, 3}:
        if algorithm == 3:
            normalized_rule = _normalize(rule)
            score = 1.0 if normalized_rule and normalized_rule in normalized_text else 0.0
        else:
            matches = sum(word in normalized_text for word in words)
            score = matches / len(words) if words else 0.0
            if algorithm == 2 and matches != len(words):
                score = 0.0
        first = min(
            (
                index
                for index, line in enumerate(lines)
                if any(word in _normalize(line) for word in words)
            ),
            default=2**31 - 1,
        )
        return score, 1, first, source

    if source == "correspondent_name":
        normalized_rule = _normalize(rule)
        if normalized_rule and normalized_rule in normalized_text:
            context_priority, first = _name_context(rule, lines)
            return 1.0, context_priority, first, source

    scored_lines = [
        (
            _line_score(
                rule,
                line,
                require_distinctive_word=source == "correspondent_name",
            ),
            index,
        )
        for index, line in enumerate(lines)
    ]
    score, line_number = max(
        scored_lines,
        default=(0.0, 2**31 - 1),
        key=lambda item: (item[0], -item[1]),
    )
    return score, 1, line_number, source


def match_correspondent(
    text: str,
    correspondents: list[ConnectorCorrespondent],
    minimum_score: float = 0.60,
) -> CorrespondentMatch | None:
    candidates: list[tuple[float, int, int, int, ConnectorCorrespondent, str]] = []
    for correspondent in correspondents:
        if _is_default_correspondent_name(correspondent.name):
            continue
        evaluated_rules = [_score_rule(correspondent, text)]
        if correspondent.match.strip():
            evaluated_rules.append(
                _score_rule(
                    ConnectorCorrespondent(
                        external_id=correspondent.external_id,
                        name=correspondent.name,
                        match="",
                        matching_algorithm=0,
                        is_insensitive=correspondent.is_insensitive,
                    ),
                    text,
                )
            )

        accepted_rules: list[tuple[float, int, int, int, str]] = []
        for score, context_priority, line_number, source in evaluated_rules:
            required_score = (
                max(minimum_score, MINIMUM_NAME_SCORE)
                if source == "correspondent_name"
                else minimum_score
            )
            if score >= required_score and not (
                source == "correspondent_name" and context_priority == 0
            ):
                value = (
                    correspondent.name if source == "correspondent_name" else correspondent.match
                )
                accepted_rules.append(
                    (score, context_priority, line_number, len(_normalize(value)), source)
                )

        if accepted_rules:
            best_rule = min(
                accepted_rules,
                key=lambda item: (-item[0], -item[1], item[2], -item[3], item[4]),
            )
            candidates.append((*best_rule[:4], correspondent, best_rule[4]))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], -item[1], item[2], -item[3], item[4].external_id))
    winner = candidates[0]
    if len(candidates) > 1 and winner[:4] == candidates[1][:4]:
        return None
    return CorrespondentMatch(
        correspondent_id=winner[4].external_id,
        name=winner[4].name,
        score=winner[0],
        source=winner[5],
        line_number=winner[2],
    )
