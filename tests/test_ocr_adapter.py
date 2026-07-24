from pathlib import Path

import pytest

from plugins.ocr.adapter import OCRAdapter
from plugins.ocr.interfaces import OCRProvider
from plugins.ocr.models import BoundingBox, OCRDocument, OCRPage, OCRWord
from plugins.ocr.paddle import PaddleOCRPlugin


class FakeProvider(OCRProvider):
    id = "fake"

    def recognize(self, document_path: Path) -> OCRDocument:
        word = OCRWord("Rechnung", 0.99, BoundingBox(1, 2, 3, 4))
        return OCRDocument(document_path, self.id, (OCRPage(1, (word,)),))


def test_adapter_returns_normalized_document(tmp_path: Path) -> None:
    source = tmp_path / "invoice.png"
    source.write_bytes(b"x")

    result = OCRAdapter(FakeProvider()).recognize(source)

    assert result.provider == "fake"
    assert result.text == "Rechnung"


def test_adapter_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        OCRAdapter(FakeProvider()).recognize(tmp_path / "missing.pdf")


def test_paddle_result_is_normalized() -> None:
    plugin = PaddleOCRPlugin()
    result = {
        "res": {
            "page_index": 0,
            "rec_texts": ["Rechnungsnummer", "2026-4711"],
            "rec_scores": [0.98, 0.96],
            "rec_boxes": [[10, 20, 110, 40], [120, 20, 220, 40]],
            "rec_polys": [
                [[10, 20], [110, 20], [110, 40], [10, 40]],
                [[120, 20], [220, 20], [220, 40], [120, 40]],
            ],
        }
    }

    page = plugin._parse_page(result, 0)

    assert page.page_number == 1
    assert page.text == "Rechnungsnummer\n2026-4711"
    assert page.words[1].bbox.x_min == 120
