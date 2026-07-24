from core.config.settings import get_settings
from plugins.ocr.adapter import OCRAdapter
from plugins.ocr.paddle import PaddleOCRPlugin


def create_ocr_adapter() -> OCRAdapter:
    settings = get_settings()
    provider = settings.ocr_provider.lower()
    if provider == "paddleocr":
        return OCRAdapter(
            PaddleOCRPlugin(
                lang=settings.ocr_language,
                device=settings.ocr_device,
            )
        )
    raise ValueError(f"Unsupported OCR provider: {settings.ocr_provider}")
