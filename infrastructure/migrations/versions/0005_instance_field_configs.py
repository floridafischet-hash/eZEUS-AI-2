"""Add tenant-specific field configurations and tenant-aware audits."""

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0005_instance_field_configs"
down_revision = "0004_ocr_artifacts"
branch_labels = None
depends_on = None

STANDARD_FIELDS = (
    ("correspondent", "Korrespondent", "text", 10, None),
    ("invoice_number", "Rechnungsnummer", "text", 20, None),
    ("invoice_date", "Rechnungsdatum", "date", 30, None),
    ("invoice_amount", "Rechnungsbetrag", "money", 40, None),
    ("customer_number", "Kundennummer", "text", 50, None),
    ("construction_site_number", "Baustellennummer", "text", 60, None),
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("instance_field_configs"):
        op.create_table(
            "instance_field_configs",
            sa.Column("instance_id", sa.Uuid(), nullable=False),
            sa.Column("field_key", sa.String(length=64), nullable=False),
            sa.Column("label", sa.String(length=255), nullable=False),
            sa.Column("field_type", sa.String(length=32), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("is_standard", sa.Boolean(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("required", sa.Boolean(), nullable=False),
            sa.Column("ocr_enabled", sa.Boolean(), nullable=False),
            sa.Column("ai_enabled", sa.Boolean(), nullable=False),
            sa.Column("external_field_id", sa.String(length=255), nullable=True),
            sa.Column("options", sa.JSON(), nullable=False),
            sa.Column("extraction_instructions", sa.String(length=2000), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["instance_id"],
                ["paperless_instances.id"],
                name=op.f("fk_instance_field_configs_instance_id_paperless_instances"),
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_instance_field_configs")),
            sa.UniqueConstraint(
                "instance_id",
                "field_key",
                name="uq_instance_field_config_key",
            ),
        )
        op.create_index(
            op.f("ix_instance_field_configs_instance_id"),
            "instance_field_configs",
            ["instance_id"],
            unique=False,
        )
        table = sa.table(
            "instance_field_configs",
            sa.column("instance_id", sa.Uuid()),
            sa.column("field_key", sa.String()),
            sa.column("label", sa.String()),
            sa.column("field_type", sa.String()),
            sa.column("sort_order", sa.Integer()),
            sa.column("is_standard", sa.Boolean()),
            sa.column("enabled", sa.Boolean()),
            sa.column("required", sa.Boolean()),
            sa.column("ocr_enabled", sa.Boolean()),
            sa.column("ai_enabled", sa.Boolean()),
            sa.column("external_field_id", sa.String()),
            sa.column("options", sa.JSON()),
            sa.column("extraction_instructions", sa.String()),
            sa.column("id", sa.Uuid()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        )
        now = datetime.now(UTC)
        rows = []
        instances = op.get_bind().execute(sa.text("SELECT id FROM paperless_instances")).fetchall()
        for (instance_id,) in instances:
            for key, label, field_type, order, external_id in STANDARD_FIELDS:
                rows.append(
                    {
                        "instance_id": instance_id,
                        "field_key": key,
                        "label": label,
                        "field_type": field_type,
                        "sort_order": order,
                        "is_standard": True,
                        "enabled": True,
                        "required": key in {"invoice_number", "invoice_amount"},
                        "ocr_enabled": True,
                        "ai_enabled": False,
                        "external_field_id": external_id,
                        "options": [],
                        "extraction_instructions": None,
                        "id": uuid4(),
                        "created_at": now,
                        "updated_at": now,
                    }
                )
        if rows:
            op.bulk_insert(table, rows)

    audit_columns = {column["name"] for column in inspector.get_columns("audit_entries")}
    if "instance_id" not in audit_columns:
        op.add_column("audit_entries", sa.Column("instance_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            op.f("fk_audit_entries_instance_id_paperless_instances"),
            "audit_entries",
            "paperless_instances",
            ["instance_id"],
            ["id"],
        )
        op.create_index(
            op.f("ix_audit_entries_instance_id"),
            "audit_entries",
            ["instance_id"],
            unique=False,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    audit_columns = {column["name"] for column in inspector.get_columns("audit_entries")}
    if "instance_id" in audit_columns:
        with op.batch_alter_table("audit_entries") as batch_op:
            batch_op.drop_index(op.f("ix_audit_entries_instance_id"))
            batch_op.drop_constraint(
                op.f("fk_audit_entries_instance_id_paperless_instances"),
                type_="foreignkey",
            )
            batch_op.drop_column("instance_id")
    if inspector.has_table("instance_field_configs"):
        op.drop_index(
            op.f("ix_instance_field_configs_instance_id"),
            table_name="instance_field_configs",
        )
        op.drop_table("instance_field_configs")
