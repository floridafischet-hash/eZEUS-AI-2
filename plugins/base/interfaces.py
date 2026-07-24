from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(slots=True)
class ExtractionCandidate:
    value: object
    confidence: float
    provider: str
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


class ExtractionProvider(ABC):
    id: str

    @abstractmethod
    async def extract(self, text: str, config: dict[str, object]) -> list[ExtractionCandidate]: ...


class Validator(ABC):
    id: str

    @abstractmethod
    def validate(self, candidate: ExtractionCandidate, config: dict[str, object]) -> bool: ...
