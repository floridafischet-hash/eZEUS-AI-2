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
    extra_data: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ConnectorCorrespondent:
    external_id: str
    name: str
    match: str
    matching_algorithm: int
    is_insensitive: bool


class DocumentConnector(ABC):
    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def get_document(self, external_document_id: str) -> ConnectorDocument: ...

    @abstractmethod
    async def write_title(self, external_document_id: str, title: str) -> bool: ...

    @abstractmethod
    async def write_correspondent_if_empty(
        self, external_document_id: str, correspondent_id: str
    ) -> bool: ...

    @abstractmethod
    async def write_empty_fields(
        self, external_document_id: str, values: dict[str, object]
    ) -> dict[str, object]: ...

    async def list_custom_fields(self) -> list[ConnectorCustomField]:
        return []

    async def create_custom_field(
        self,
        name: str,
        data_type: str,
        options: list[str] | None = None,
    ) -> ConnectorCustomField:
        raise NotImplementedError

    async def update_custom_field(
        self,
        external_field_id: str,
        name: str,
        data_type: str,
        options: list[str] | None = None,
    ) -> ConnectorCustomField:
        raise NotImplementedError

    async def list_correspondents(self) -> list[ConnectorCorrespondent]:
        return []
