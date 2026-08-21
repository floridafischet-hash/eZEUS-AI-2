from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.config.settings import get_settings

app = FastAPI(title="Paperless API Mock")
fixture = Path(__file__).parents[2] / "tests" / "fixtures" / "invoice.pdf"
document: dict[str, object] = {
    "id": 128,
    "title": "Testrechnung",
    "original_file_name": "invoice.pdf",
    "mime_type": "application/pdf",
    "document_type": 7,
    "correspondent": None,
    "content": "Rechnungsnummer: RE-2026-128\nGesamtbetrag: 123,45 EUR",
    "custom_fields": [
        {"field": 14, "value": None},
        {"field": 15, "value": None},
        {"field": 99, "value": "manuell"},
    ],
}
write_log: list[dict[str, object]] = []


class PatchDocument(BaseModel):
    title: str | None = None
    correspondent: int | None = None
    content: str | None = None
    custom_fields: list[dict[str, object]] | None = None


def authenticate(authorization: Annotated[str | None, Header()] = None) -> None:
    configured_token = get_settings().paperless_api_token or "mock-paperless-token"
    if authorization != f"Token {configured_token}":
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/api/documents/")
def list_documents(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    authenticate(authorization)
    return {"count": 1, "results": [document]}


@app.get("/api/documents/128/")
def get_document(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    authenticate(authorization)
    return document


@app.get("/api/documents/128/download/")
def download_document(
    authorization: Annotated[str | None, Header()] = None,
) -> FileResponse:
    authenticate(authorization)
    return FileResponse(fixture, media_type="application/pdf", filename="invoice.pdf")


@app.get("/api/custom_fields/")
def list_custom_fields(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    authenticate(authorization)
    return {
        "count": 2,
        "next": None,
        "results": [
            {"id": 14, "name": "Rechnungsnummer", "data_type": "string"},
            {
                "id": 15,
                "name": "Rechnungsbetrag",
                "data_type": "monetary",
                "extra_data": {"default_currency": "EUR"},
            },
        ],
    }


@app.get("/api/correspondents/")
def list_correspondents(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    authenticate(authorization)
    return {"count": 0, "next": None, "results": []}


@app.patch("/api/documents/128/")
def patch_document(
    payload: PatchDocument,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    authenticate(authorization)
    changes = payload.model_dump(exclude_none=True)
    document.update(changes)
    write_log.append(changes)
    return document


@app.get("/debug/state")
def debug_state() -> dict[str, object]:
    return {"document": document, "writes": write_log}
