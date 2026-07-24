from plugins.base.interfaces import ExtractionCandidate, Validator


class ConfidenceValidator(Validator):
    id = "confidence"

    def validate(self, candidate: ExtractionCandidate, config: dict[str, object]) -> bool:
        minimum = float(str(config.get("minimum", 0.8)))
        return candidate.confidence >= minimum
