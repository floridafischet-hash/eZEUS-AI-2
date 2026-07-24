from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from plugins.ocr.interfaces import OCRProvider
from plugins.ocr.models import BoundingBox, OCRDocument, OCRPage, OCRWord


class PaddleOCRPlugin(OCRProvider):
    id = "paddleocr"

    def __init__(
        self,
        *,
        lang: str = "de",
        device: str = "cpu",
        use_doc_orientation_classify: bool = True,
        use_doc_unwarping: bool = True,
        use_textline_orientation: bool = True,
    ) -> None:
        self.lang = {"de": "german"}.get(lang.lower(), lang)
        self.device = device
        self.use_doc_orientation_classify = use_doc_orientation_classify
        self.use_doc_unwarping = use_doc_unwarping
        self.use_textline_orientation = use_textline_orientation
        self._pipeline: Any | None = None

    def _get_pipeline(self) -> Any:
        if self._pipeline is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise RuntimeError(
                    "PaddleOCR is not installed. Install the 'ocr-paddle' project extra "
                    "or use Dockerfile.paddle."
                ) from exc

            self._pipeline = PaddleOCR(
                lang=self.lang,
                device=self.device,
                enable_mkldnn=False,
                use_doc_orientation_classify=self.use_doc_orientation_classify,
                use_doc_unwarping=self.use_doc_unwarping,
                use_textline_orientation=self.use_textline_orientation,
            )
        return self._pipeline

    def recognize(self, document_path: Path) -> OCRDocument:
        pipeline = self._get_pipeline()
        raw_results = pipeline.predict(input=str(document_path))
        pages = tuple(self._parse_page(result, index) for index, result in enumerate(raw_results))
        return OCRDocument(
            source=document_path,
            provider=self.id,
            pages=pages,
            metadata={"language": self.lang, "device": self.device},
        )

    def _parse_page(self, result: Any, fallback_index: int) -> OCRPage:
        payload = self._to_mapping(result)
        data = payload.get("res", payload)
        if not isinstance(data, Mapping):
            raise ValueError("Unexpected PaddleOCR result payload")

        texts = self._as_list(data.get("rec_texts", []))
        scores = self._as_list(data.get("rec_scores", []))
        boxes = self._as_list(data.get("rec_boxes", []))
        polygons = self._as_list(data.get("rec_polys", []))

        words: list[OCRWord] = []
        for index, text in enumerate(texts):
            clean_text = str(text).strip()
            if not clean_text:
                continue
            score = float(scores[index]) if index < len(scores) else 0.0
            polygon = self._normalize_polygon(polygons[index]) if index < len(polygons) else ()
            bbox = (
                self._normalize_box(boxes[index])
                if index < len(boxes)
                else self._bbox_from_polygon(polygon)
            )
            words.append(
                OCRWord(
                    text=clean_text,
                    confidence=max(0.0, min(score, 1.0)),
                    bbox=bbox,
                    polygon=polygon,
                )
            )

        page_index = data.get("page_index")
        page_number = int(page_index) + 1 if page_index is not None else fallback_index + 1
        return OCRPage(page_number=page_number, words=tuple(words))

    @staticmethod
    def _to_mapping(result: Any) -> Mapping[str, Any]:
        value = getattr(result, "json", result)
        if callable(value):
            value = value()
        if not isinstance(value, Mapping):
            raise ValueError("PaddleOCR result does not expose a JSON mapping")
        return value

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, list):
            return value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return list(value)
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray, Mapping)):
            return list(value)
        return []

    @classmethod
    def _normalize_polygon(cls, value: Any) -> tuple[tuple[float, float], ...]:
        points = cls._as_list(value)
        normalized: list[tuple[float, float]] = []
        for point in points:
            pair = cls._as_list(point)
            if len(pair) >= 2:
                normalized.append((float(pair[0]), float(pair[1])))
        return tuple(normalized)

    @staticmethod
    def _normalize_box(value: Any) -> BoundingBox:
        raw = value.tolist() if hasattr(value, "tolist") else value
        if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or len(raw) < 4:
            raise ValueError(f"Invalid PaddleOCR bounding box: {raw!r}")
        return BoundingBox(float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))

    @staticmethod
    def _bbox_from_polygon(polygon: tuple[tuple[float, float], ...]) -> BoundingBox:
        if not polygon:
            return BoundingBox(0.0, 0.0, 0.0, 0.0)
        xs = [point[0] for point in polygon]
        ys = [point[1] for point in polygon]
        return BoundingBox(min(xs), min(ys), max(xs), max(ys))
