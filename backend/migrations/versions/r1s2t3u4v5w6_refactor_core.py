"""Refactor core: binary assets, intake, review stage, job leases."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r1s2t3u4v5w6_refactor_core"
down_revision: Union[str, None] = "q4r5s6t7u8v9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE asset_domain AS ENUM ('reference', 'figure', 'export_temp', 'misc')")
    op.execute(
        "CREATE TYPE asset_role AS ENUM "
        "('original_upload', 'figure_png', 'figure_svg', 'source', 'thumbnail', 'export_png')"
    )
    op.execute(
        "CREATE TYPE figure_asset_role AS ENUM ('primary', 'png', 'svg', 'source', 'thumbnail', 'export_png')"
    )
    op.execute(
        "CREATE TYPE creation_origin AS ENUM "
        "('idea_only', 'material_first', 'outline_first', 'manuscript_continue')"
    )
    op.execute(
        "CREATE TYPE intake_status AS ENUM ('collecting', 'understanding_ready', 'confirmed', 'superseded')"
    )
    op.execute("CREATE TYPE intake_item_type AS ENUM ('natural_text', 'pasted_text', 'upload')")
    op.execute("CREATE TYPE intake_item_status AS ENUM ('pending', 'parsed', 'failed', 'disabled')")
    op.execute("CREATE TYPE understanding_status AS ENUM ('draft', 'confirmed', 'superseded')")
    op.execute("CREATE TYPE writing_plan_status AS ENUM ('draft', 'confirmed', 'superseded')")
    op.execute(
        "CREATE TYPE review_stage_status AS ENUM ('not_started', 'running', 'completed', 'failed')"
    )
    op.execute("CREATE TYPE review_track AS ENUM ('writing_quality', 'publication_standard')")
    op.execute("CREATE TYPE review_finding_status AS ENUM ('open', 'resolved', 'dismissed')")

    op.create_table(
        "binary_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_domain", postgresql.ENUM(name="asset_domain", create_type=False), nullable=False),
        sa.Column("asset_role", postgresql.ENUM(name="asset_role", create_type=False), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("extension", sa.String(32), nullable=True),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_binary_assets_book_id", "binary_assets", ["book_id"])
    op.create_index("ix_binary_assets_sha256", "binary_assets", ["sha256"])

    op.create_table(
        "figure_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("figure_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("figures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("binary_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", postgresql.ENUM(name="figure_asset_role", create_type=False), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.add_column("reference_files", sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_reference_files_asset_id",
        "reference_files",
        "binary_assets",
        ["asset_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.alter_column("reference_files", "storage_path", existing_type=sa.String(2000), nullable=True)

    op.add_column("books", sa.Column("creation_origin", postgresql.ENUM(name="creation_origin", create_type=False), nullable=True))

    op.create_table(
        "project_intakes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creation_origin", postgresql.ENUM(name="creation_origin", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM(name="intake_status", create_type=False), nullable=False),
        sa.Column("raw_goal_text", sa.Text(), nullable=True),
        sa.Column("negative_constraints_text", sa.Text(), nullable=True),
        sa.Column("confirmed_understanding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confirmed_writing_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "intake_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_intakes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", postgresql.ENUM(name="intake_item_type", create_type=False), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("binary_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("filename", sa.String(500), nullable=True),
        sa.Column("parsed_preview", sa.Text(), nullable=True),
        sa.Column("detected_roles", postgresql.JSONB(), nullable=True),
        sa.Column("status", postgresql.ENUM(name="intake_item_status", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "input_understandings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_intakes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("summary_json", postgresql.JSONB(), nullable=True),
        sa.Column("user_facing_text", sa.Text(), nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=True),
        sa.Column("preserve_rules", postgresql.JSONB(), nullable=True),
        sa.Column("editable_rules", postgresql.JSONB(), nullable=True),
        sa.Column("avoid_rules", postgresql.JSONB(), nullable=True),
        sa.Column("unclear_questions", postgresql.JSONB(), nullable=True),
        sa.Column("status", postgresql.ENUM(name="understanding_status", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "writing_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intake_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_intakes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("understanding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("input_understandings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("plan_json", postgresql.JSONB(), nullable=True),
        sa.Column("user_facing_text", sa.Text(), nullable=True),
        sa.Column("impact_map", postgresql.JSONB(), nullable=True),
        sa.Column("status", postgresql.ENUM(name="writing_plan_status", create_type=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "book_review_stage_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", postgresql.ENUM(name="review_stage_status", create_type=False), nullable=False),
        sa.Column("writing_quality_status", postgresql.ENUM(name="review_stage_status", create_type=False), nullable=True),
        sa.Column("publication_standard_status", postgresql.ENUM(name="review_stage_status", create_type=False), nullable=True),
        sa.Column("summary_json", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "book_review_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("book_review_stage_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("track", postgresql.ENUM(name="review_track", create_type=False), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("status", postgresql.ENUM(name="review_finding_status", create_type=False), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("source_ref_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    for table, cols in (
        ("book_jobs", ["lease_owner", "lease_until", "heartbeat_at"]),
        ("figure_batch_runs", ["lease_owner", "lease_until", "heartbeat_at"]),
        ("optimization_jobs", ["lease_owner", "lease_until", "heartbeat_at"]),
    ):
        op.add_column(table, sa.Column("lease_owner", sa.String(128), nullable=True))
        op.add_column(table, sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table in ("optimization_jobs", "figure_batch_runs", "book_jobs"):
        op.drop_column(table, "heartbeat_at")
        op.drop_column(table, "lease_until")
        op.drop_column(table, "lease_owner")

    op.drop_table("book_review_findings")
    op.drop_table("book_review_stage_runs")
    op.drop_table("writing_plans")
    op.drop_table("input_understandings")
    op.drop_table("intake_items")
    op.drop_table("project_intakes")
    op.drop_column("books", "creation_origin")
    op.drop_constraint("fk_reference_files_asset_id", "reference_files", type_="foreignkey")
    op.drop_column("reference_files", "asset_id")
    op.alter_column("reference_files", "storage_path", existing_type=sa.String(2000), nullable=False)
    op.drop_table("figure_assets")
    op.drop_table("binary_assets")

    for name in (
        "review_finding_status",
        "review_track",
        "review_stage_status",
        "writing_plan_status",
        "understanding_status",
        "intake_item_status",
        "intake_item_type",
        "intake_status",
        "creation_origin",
        "figure_asset_role",
        "asset_role",
        "asset_domain",
    ):
        op.execute(f"DROP TYPE IF EXISTS {name}")
