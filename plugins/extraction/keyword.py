from plugins.base.interfaces import ExtractionCandidate, ExtractionProvider


class KeywordExtractionProvider(ExtractionProvider):
    id = "keyword"

    async def extract(self, text: str, config: dict[str, object]) -> list[ExtractionCandidate]:
        case_sensitive = bool(config.get("case_sensitive", False))
        configured_keywords = config.get("keywords", [])
        configured_synonyms = config.get("synonyms", [])
        raw_keywords = [
            *(configured_keywords if isinstance(configured_keywords, list) else []),
            *(configured_synonyms if isinstance(configured_synonyms, list) else []),
        ]
        keywords = [str(item) if case_sensitive else str(item).lower() for item in raw_keywords]
        before = int(str(config.get("context_before", 2)))
        after = int(str(config.get("context_after", 3)))
        lines = text.splitlines()
        results: list[ExtractionCandidate] = []
        for index, line in enumerate(lines):
            comparable = line if case_sensitive else line.lower()
            matched = [keyword for keyword in keywords if keyword in comparable]
            if matched:
                context = "\n".join(lines[max(0, index - before) : index + after + 1])
                results.append(
                    ExtractionCandidate(
                        value=context,
                        confidence=0.6,
                        provider=self.id,
                        metadata={"line": index + 1, "keywords": matched},
                    )
                )
        return results
