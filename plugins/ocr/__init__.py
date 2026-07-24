from plugins.ocr.adapter import OCRAdapter
from plugins.ocr.interfaces import OCRProvider
from plugins.ocr.models import BoundingBox, OCRDocument, OCRPage, OCRWord
from plugins.ocr.paddle import PaddleOCRPlugin

__all__ = [
    "BoundingBox",
    "OCRAdapter",
    "OCRDocument",
    "OCRPage",
    "OCRProvider",
    "OCRWord",
    "PaddleOCRPlugin",
]
