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
        candidates: list[ExtractionCandidate] = []
        seen: set[tuple[str, int]] = set()
        for pattern in patterns:
            try:
                compiled = regex.compile(str(pattern), flags=regex.MULTILINE)
            except regex.error as exc:
                raise ValueError(f"Invalid extraction pattern: {exc}") from exc
            try:
                for match in compiled.finditer(text, timeout=pattern_timeout):
                    if monotonic() - started > hard_timeout:
                        raise TimeoutError("Regex extraction time limit exceeded")
                    value = (
                        match.group(group)
                        if match.lastindex and group <= match.lastindex
                        else match.group(0)
                    )
                    cleaned_value = value.strip()
                    candidate_key = (cleaned_value, match.start())
                    if candidate_key in seen:
                        continue
                    seen.add(candidate_key)
                    candidates.append(
                        ExtractionCandidate(
                            value=cleaned_value,
                            confidence=0.95 if match.lastindex else 0.85,
                            provider=self.id,
                            metadata={"pattern": str(pattern), "offset": match.start()},
                        )
                    )
            except TimeoutError as exc:
                raise TimeoutError("Regex extraction hard time limit exceeded") from exc
        return candidates
