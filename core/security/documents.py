from core.config.settings import Settings, get_settings


class DocumentSafetyError(ValueError):
    pass


def validate_paperless_document(
    *,
    mime_type: str | None,
    content: str | None,
    settings: Settings | None = None,
) -> None:
    """Validate the metadata and OCR text eZEUS receives from Paperless.

    eZEUS does not download or parse document binaries.  That removes the PDF
    bomb and malware-parser attack surface from this service; the remaining
    untrusted input is Paperless metadata plus OCR text and is capped here.
    """

    runtime = settings or get_settings()
    normalized_mime = (mime_type or "").partition(";")[0].strip().lower()
    allowed = {item.lower() for item in runtime.allowed_document_mime_types}
    if normalized_mime and normalized_mime not in allowed:
        raise DocumentSafetyError(f"Unsupported document MIME type: {normalized_mime}")
    if content is not None and len(content) > runtime.paperless_max_text_chars:
        raise DocumentSafetyError(
            f"Paperless OCR text exceeds {runtime.paperless_max_text_chars} characters"
        )
