from pathlib import Path

from plugins.ocr.interfaces import OCRProvider
from plugins.ocr.models import OCRDocument


class OCRAdapter:
    def __init__(self, provider: OCRProvider) -> None:
        self.provider = provider

    def recognize(self, document_path: Path) -> OCRDocument:
        if not document_path.exists():
            raise FileNotFoundError(document_path)
        if not document_path.is_file():
            raise ValueError(f"OCR input is not a file: {document_path}")

        result = self.provider.recognize(document_path)
        if result.provider != self.provider.id:
            raise ValueError(
                f"OCR provider mismatch: expected {self.provider.id!r}, got {result.provider!r}"
            )
        return result
