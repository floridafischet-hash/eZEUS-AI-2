from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float


@dataclass(frozen=True, slots=True)
class OCRWord:
    text: str
    confidence: float
    bbox: BoundingBox
    polygon: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True, slots=True)
class OCRPage:
    page_number: int
    words: tuple[OCRWord, ...]
    width: int | None = None
    height: int | None = None

    @property
    def text(self) -> str:
        return "\n".join(word.text for word in self.words if word.text.strip())


@dataclass(frozen=True, slots=True)
class OCRDocument:
    source: Path
    provider: str
    pages: tuple[OCRPage, ...]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages if page.text.strip())
