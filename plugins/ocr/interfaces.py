from abc import ABC, abstractmethod
from pathlib import Path

from plugins.ocr.models import OCRDocument


class OCRProvider(ABC):
    id: str

    @abstractmethod
    def recognize(self, document_path: Path) -> OCRDocument: ...
