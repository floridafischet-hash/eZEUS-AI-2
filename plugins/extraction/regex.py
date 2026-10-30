import html
import re
from time import monotonic

import regex

from core.config.settings import get_settings
from plugins.base.interfaces import ExtractionCandidate, ExtractionProvider


class RegexExtractionProvider(ExtractionProvider):
    id = "regex"

    @staticmethod
    def _normalize_document_text(text: str) -> str:
        """Flatten Paperless Markdown/HTML without losing table row boundaries."""
        normalized = html.unescape(text)
        normalized = re.sub(r"(?i)<br\s*/?>", " ", normalized)
        normalized = re.sub(
            r"(?is)</(?:td|th)>\s*<(?:td|th)(?:\s[^>]*)?>",
            " ",
            normalized,
        )
        normalized = re.sub(
            r"(?is)</tr>(?:\s*</?(?:thead|tbody)>\s*)*<tr(?:\s[^>]*)?>",
            "\n",
            normalized,
        )
        normalized = re.sub(r"(?is)</(?:p|div|table|thead|tbody|h[1-6])>", "\n", normalized)
        normalized = re.sub(r"(?is)<[^>]+>", "", normalized)
        normalized = normalized.replace("**", "").replace("__", "")
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r" *\n *", "\n", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    async def extract(self, text: str, config: dict[str, object]) -> list[ExtractionCandidate]:
        text = self._normalize_document_text(text)
        patterns = config.get("patterns")
        if not isinstance(patterns, list):
            pattern = str(config.get("pattern", ""))
            patterns = [pattern] if pattern else []
        group = int(str(config.get("group", 1)))
        timeout_ms = int(str(config.get("timeout_ms", 250)))
        hard_timeout = get_settings().regex_hard_timeout_seconds
        pattern_timeout = min(max(timeout_ms / 1000, 0.001), hard_timeout)
        started = monotonic()
        negative_context = False
        configured_negative_patterns = config.get("negative_context_patterns", [])
        negative_patterns = (
            configured_negative_patterns if isinstance(configured_negative_patterns, list) else []
        )
        for negative_pattern in negative_patterns:
            remaining = hard_timeout - (monotonic() - started)
            if remaining <= 0:
                raise TimeoutError("Regex extraction hard time limit exceeded")
            try:
                compiled_negative = regex.compile(str(negative_pattern), flags=regex.MULTILINE)
                if compiled_negative.search(text, timeout=min(pattern_timeout, remaining)):
                    negative_context = True
                    break
            except regex.error as exc:
                raise ValueError(f"Invalid negative-context pattern: {exc}") from exc
            except TimeoutError as exc:
                raise TimeoutError("Regex extraction hard time limit exceeded") from exc
        candidates: list[ExtractionCandidate] = []
        seen: set[tuple[str, int]] = set()
        for pattern_index, pattern in enumerate(patterns):
            remaining = hard_timeout - (monotonic() - started)
            if remaining <= 0:
                raise TimeoutError("Regex extraction hard time limit exceeded")
            try:
                compiled = regex.compile(str(pattern), flags=regex.MULTILINE)
            except regex.error as exc:
                raise ValueError(f"Invalid extraction pattern: {exc}") from exc
            try:
                for match in compiled.finditer(text, timeout=min(pattern_timeout, remaining)):
                    if monotonic() - started > hard_timeout:
                        raise TimeoutError("Regex extraction time limit exceeded")
                    if not match.lastindex or group < 1 or group > match.lastindex:
                        raise ValueError(
                            f"Extraction group {group} is unavailable for pattern {pattern_index}"
                        )
                    value = match.group(group)
                    cleaned_value = value.strip()
                    cleaned_value = cleaned_value.replace("−", "-").replace("–", "-")
                    if (
                        negative_context
                        and bool(config.get("negate_on_negative_context"))
                        and not cleaned_value.startswith("-")
                    ):
                        cleaned_value = f"-{cleaned_value}"
                    candidate_key = (cleaned_value, match.start())
                    if candidate_key in seen:
                        continue
                    seen.add(candidate_key)
                    candidates.append(
                        ExtractionCandidate(
                            value=cleaned_value,
                            confidence=0.95 if match.lastindex else 0.85,
                            provider=self.id,
                            metadata={
                                "pattern": str(pattern),
                                "pattern_index": pattern_index,
                                "offset": match.start(),
                            },
                        )
                    )
            except TimeoutError as exc:
                raise TimeoutError("Regex extraction hard time limit exceeded") from exc
        return candidates
