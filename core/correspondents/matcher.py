import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

import regex

from connectors.base.interface import ConnectorCorrespondent
from core.config.settings import get_settings


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


def _line_score(rule: str, line: str) -> float:
    normalized_rule = _normalize(rule)
    normalized_line = _normalize(line)
    if not normalized_rule or not normalized_line:
        return 0.0
    if normalized_rule in normalized_line:
        return 1.0
    if len(normalized_rule.split()) == 1:
        return 0.0
    return SequenceMatcher(None, normalized_rule, normalized_line).ratio()


def _score_rule(correspondent: ConnectorCorrespondent, text: str) -> tuple[float, int, str]:
    rule = correspondent.match.strip() or correspondent.name.strip()
    source = "matching_rule" if correspondent.match.strip() else "correspondent_name"
    if not rule:
        return 0.0, 2**31 - 1, source
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
            return 0.0, 2**31 - 1, source
        if match is None:
            return 0.0, 2**31 - 1, source
        line_number = text[: match.start()].count("\n")
        return 1.0, line_number, source

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
        return score, first, source

    scored_lines = [(_line_score(rule, line), index) for index, line in enumerate(lines)]
    return max(scored_lines, default=(0.0, 2**31 - 1), key=lambda item: (item[0], -item[1])) + (
        source,
    )


def match_correspondent(
    text: str,
    correspondents: list[ConnectorCorrespondent],
    minimum_score: float = 0.60,
) -> CorrespondentMatch | None:
    candidates: list[tuple[float, int, int, ConnectorCorrespondent, str]] = []
    for correspondent in correspondents:
        score, line_number, source = _score_rule(correspondent, text)
        if score >= minimum_score:
            specificity = len(_normalize(correspondent.match or correspondent.name))
            candidates.append((score, line_number, specificity, correspondent, source))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1], -item[2], item[3].external_id))
    winner = candidates[0]
    if len(candidates) > 1 and winner[:3] == candidates[1][:3]:
        return None
    return CorrespondentMatch(
        correspondent_id=winner[3].external_id,
        name=winner[3].name,
        score=winner[0],
        source=winner[4],
        line_number=winner[1],
    )
