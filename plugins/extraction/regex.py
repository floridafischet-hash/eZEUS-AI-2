import re
from time import monotonic

from plugins.base.interfaces import ExtractionCandidate, ExtractionProvider


class RegexExtractionProvider(ExtractionProvider):
    id = "regex"

    async def extract(self, text: str, config: dict[str, object]) -> list[ExtractionCandidate]:
        patterns = config.get("patterns")
        if not isinstance(patterns, list):
            pattern = str(config.get("pattern", ""))
            patterns = [pattern] if pattern else []
        group = int(str(config.get("group", 1)))
        timeout_ms = int(str(config.get("timeout_ms", 250)))
        started = monotonic()
        candidates: list[ExtractionCandidate] = []
        for pattern in patterns:
            try:
                compiled = re.compile(str(pattern), flags=re.MULTILINE)
            except re.error as exc:
                raise ValueError(f"Invalid extraction pattern: {exc}") from exc
            for match in compiled.finditer(text):
                if (monotonic() - started) * 1000 > timeout_ms:
                    raise TimeoutError("Regex extraction time limit exceeded")
                value = (
                    match.group(group)
                    if match.lastindex and group <= match.lastindex
                    else match.group(0)
                )
                candidates.append(
                    ExtractionCandidate(
                        value=value.strip(),
                        confidence=0.95 if match.lastindex else 0.85,
                        provider=self.id,
                        metadata={"pattern": str(pattern), "offset": match.start()},
                    )
                )
        return candidates
