from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(slots=True)
class ConnectorDocument:
    external_id: str
    title: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    document_type_id: str | None = None
    correspondent_id: str | None = None
    content: str | None = None
    custom_fields: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ConnectorCustomField:
    external_id: str
    name: str
    data_type: str


class DocumentConnector(ABC):
    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def get_document(self, external_document_id: str) -> ConnectorDocument: ...

    @abstractmethod
    async def download_original(self, external_document_id: str) -> bytes: ...

    @abstractmethod
    async def write_content(self, external_document_id: str, content: str) -> bool: ...

    @abstractmethod
    async def write_title(self, external_document_id: str, title: str) -> bool: ...

    @abstractmethod
    async def write_empty_fields(
        self, external_document_id: str, values: dict[str, object]
    ) -> dict[str, object]: ...

    async def list_custom_fields(self) -> list[ConnectorCustomField]:
        return []
