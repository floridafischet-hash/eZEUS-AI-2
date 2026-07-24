from sqlalchemy import select
from sqlalchemy.orm import Session

from core.models.template import Template
from core.templates.schema import TemplateConfig


class TemplateService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def select_for_document_type(
        self, document_type_id: str | None
    ) -> tuple[Template, TemplateConfig] | None:
        if not document_type_id:
            return None
        template = self.db.scalar(
            select(Template)
            .where(
                Template.document_type_external_id == document_type_id,
                Template.enabled.is_(True),
            )
            .order_by(Template.is_default.desc(), Template.version.desc())
        )
        if template is None:
            return None
        return template, TemplateConfig.model_validate(template.config)
