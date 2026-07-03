"""AutoBooker 0.5 material, optimization, citation and figure batch core.

Revision ID: p3q4r5s6t7u8
Revises: o2p3q4r5s6t7
Create Date: 2026-07-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p3q4r5s6t7u8"
down_revision: Union[str, None] = "o2p3q4r5s6t7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE book_workflow_mode AS ENUM ('from_scratch', 'optimize_existing')")
    op.execute(
        "CREATE TYPE file_lifecycle_status AS ENUM "
        "('processing', 'pending_confirmation', 'effective', 'disabled', 'failed')"
    )
    op.execute(
        "CREATE TYPE file_purpose AS ENUM "
        "('outline', 'writing_requirements', 'reference_material', 'bibliography', 'source_manuscript')"
    )
    op.execute("CREATE TYPE material_confirmation_status AS ENUM ('effective', 'pending', 'disabled')")
    op.execute(
        "CREATE TYPE optimization_status AS ENUM "
        "('parsing', 'mapping_review', 'ready_for_analysis', 'analyzing', 'plan_ready', "
        "'optimizing', 'editing', 'completed', 'failed')"
    )

    op.add_column(
        "books",
        sa.Column(
            "workflow_mode",
            postgresql.ENUM(name="book_workflow_mode", create_type=False),
            nullable=False,
            server_default="from_scratch",
        ),
    )
    op.add_column(
        "books",
        sa.Column("structured_citations", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "reference_files",
        sa.Column(
            "lifecycle_status",
            postgresql.ENUM(name="file_lifecycle_status", create_type=False),
            nullable=False,
            server_default="processing",
        ),
    )
    op.add_column("reference_files", sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))

    for name, col in (
        ("chunk_kind", sa.Column("chunk_kind", sa.String(32), nullable=False, server_default="reference_material")),
        ("page_number", sa.Column("page_number", sa.Integer(), nullable=True)),
        ("paragraph_index", sa.Column("paragraph_index", sa.Integer(), nullable=True)),
        ("heading_path", sa.Column("heading_path", postgresql.JSONB(), nullable=True)),
        ("directly_quotable", sa.Column("directly_quotable", sa.Boolean(), nullable=False, server_default="false")),
        ("active", sa.Column("active", sa.Boolean(), nullable=False, server_default="true")),
    ):
        op.add_column("reference_chunks", col)

    op.create_table(
        "reference_file_purposes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reference_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", postgresql.ENUM(name="file_purpose", create_type=False), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("file_id", "purpose", name="uq_reference_file_purpose"),
    )
    op.create_index("ix_reference_file_purposes_file_id", "reference_file_purposes", ["file_id"])

    op.create_table(
        "writing_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reference_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("strength", sa.String(20), nullable=False, server_default="should"),
        sa.Column("scope", sa.String(20), nullable=False, server_default="book"),
        sa.Column("chapter_index", sa.Integer(), nullable=True),
        sa.Column("confirmation_status", postgresql.ENUM(name="material_confirmation_status", create_type=False), nullable=False, server_default="effective"),
        sa.Column("validation_kind", sa.String(64), nullable=True),
        sa.Column("validation_config", postgresql.JSONB(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_writing_requirements_book_id", "writing_requirements", ["book_id"])
    op.create_index("ix_writing_requirements_source_file_id", "writing_requirements", ["source_file_id"])

    op.create_table(
        "material_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reference_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term", sa.String(300), nullable=False),
        sa.Column("canonical_form", sa.String(300), nullable=True),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("term_type", sa.String(40), nullable=False, server_default="domain_term"),
        sa.Column("confirmation_status", postgresql.ENUM(name="material_confirmation_status", create_type=False), nullable=False, server_default="effective"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_material_terms_book_id", "material_terms", ["book_id"])
    op.create_index("ix_material_terms_source_file_id", "material_terms", ["source_file_id"])

    op.create_table(
        "material_conflicts_v2",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conflict_type", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("file_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("resolution", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_material_conflicts_v2_book_id", "material_conflicts_v2", ["book_id"])

    op.create_table(
        "outline_constraints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reference_files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_index", sa.Integer(), nullable=False),
        sa.Column("chapter_title", sa.String(500), nullable=False),
        sa.Column("locked_sections", postgresql.JSONB(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_outline_constraints_book_id", "outline_constraints", ["book_id"])
    op.create_index("ix_outline_constraints_source_file_id", "outline_constraints", ["source_file_id"])

    op.create_table(
        "requirement_validations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("writing_requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    for name, col in (
        ("document_type", sa.Column("document_type", sa.String(80), nullable=True)),
        ("publisher", sa.Column("publisher", sa.String(500), nullable=True)),
        ("volume", sa.Column("volume", sa.String(80), nullable=True)),
        ("issue", sa.Column("issue", sa.String(80), nullable=True)),
        ("pages", sa.Column("pages", sa.String(120), nullable=True)),
        ("metadata_status", sa.Column("metadata_status", sa.String(32), nullable=False, server_default="complete")),
    ):
        op.add_column("citations", col)

    op.create_table(
        "citation_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("citation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("citations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reference_files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reference_chunks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("paragraph_locator", sa.String(300), nullable=True),
        sa.Column("heading_path", postgresql.JSONB(), nullable=True),
        sa.Column("quote_text", sa.Text(), nullable=False),
        sa.Column("directly_quotable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_citation_evidence_citation_id", "citation_evidence", ["citation_id"])

    op.create_table(
        "citation_occurrences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("citation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("citations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("citation_evidence.id", ondelete="SET NULL"), nullable=True),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cite_mode", sa.String(24), nullable=False, server_default="parenthetical"),
        sa.Column("locator", sa.String(300), nullable=True),
        sa.Column("prefix", sa.Text(), nullable=True),
        sa.Column("suffix", sa.Text(), nullable=True),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context_before", sa.Text(), nullable=True),
        sa.Column("context_after", sa.Text(), nullable=True),
        sa.Column("complete", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("chapter_id", "node_id", name="uq_citation_occurrence_node"),
    )
    op.create_index("ix_citation_occurrences_book_id", "citation_occurrences", ["book_id"])
    op.create_index("ix_citation_occurrences_chapter_id", "citation_occurrences", ["chapter_id"])
    op.create_index("ix_citation_occurrences_citation_id", "citation_occurrences", ["citation_id"])

    op.create_table(
        "optimization_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("reference_files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", postgresql.ENUM(name="optimization_status", create_type=False), nullable=False, server_default="parsing"),
        sa.Column("allow_structure_changes", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("optimization_goals", postgresql.JSONB(), nullable=True),
        sa.Column("diagnosis", postgresql.JSONB(), nullable=True),
        sa.Column("optimization_plan", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("baseline_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "manuscript_baseline_chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("optimization_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("heading_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_locator", postgresql.JSONB(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("project_id", "original_index", name="uq_baseline_project_index"),
    )
    op.create_index("ix_manuscript_baseline_chapters_project_id", "manuscript_baseline_chapters", ["project_id"])
    op.create_table(
        "manuscript_chapter_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("optimization_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("baseline_chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("manuscript_baseline_chapters.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("working_chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("outline_chapter_index", sa.Integer(), nullable=True),
        sa.Column("outline_title", sa.String(500), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("status", sa.String(32), nullable=False, server_default="auto_confirmed"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_manuscript_chapter_mappings_project_id", "manuscript_chapter_mappings", ["project_id"])
    op.create_table(
        "manuscript_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("optimization_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("baseline_chapter_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("manuscript_baseline_chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_revision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("manuscript_revisions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="ai_optimization"),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("tiptap_json", postgresql.JSONB(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="proposed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_manuscript_revisions_project_id", "manuscript_revisions", ["project_id"])
    op.create_index("ix_manuscript_revisions_baseline_chapter_id", "manuscript_revisions", ["baseline_chapter_id"])
    op.create_table(
        "optimization_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("optimization_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("current_chapter_index", sa.Integer(), nullable=True),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_optimization_jobs_project_id", "optimization_jobs", ["project_id"])
    op.create_index(
        "uq_optimization_jobs_active_project",
        "optimization_jobs",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )

    op.create_table(
        "figure_batch_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_index", sa.Integer(), nullable=True),
        sa.Column("trigger", sa.String(24), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_figure_batch_runs_book_id", "figure_batch_runs", ["book_id"])
    op.create_table(
        "figure_batch_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("figure_batch_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("figure_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("figures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_id", "figure_id", name="uq_figure_batch_run_figure"),
    )
    op.create_index("ix_figure_batch_items_run_id", "figure_batch_items", ["run_id"])
    op.create_index("ix_figure_batch_items_figure_id", "figure_batch_items", ["figure_id"])
    op.create_index(
        "uq_figure_batch_active_figure",
        "figure_batch_items",
        ["figure_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    for table in (
        "figure_batch_items",
        "figure_batch_runs",
        "optimization_jobs",
        "manuscript_revisions",
        "manuscript_chapter_mappings",
        "manuscript_baseline_chapters",
        "optimization_projects",
        "citation_occurrences",
        "citation_evidence",
        "requirement_validations",
        "outline_constraints",
        "material_conflicts_v2",
        "material_terms",
        "writing_requirements",
        "reference_file_purposes",
    ):
        op.drop_table(table)
    for col in ("metadata_status", "pages", "issue", "volume", "publisher", "document_type"):
        op.drop_column("citations", col)
    for col in ("active", "directly_quotable", "heading_path", "paragraph_index", "page_number", "chunk_kind"):
        op.drop_column("reference_chunks", col)
    op.drop_column("reference_files", "disabled_at")
    op.drop_column("reference_files", "lifecycle_status")
    op.drop_column("books", "structured_citations")
    op.drop_column("books", "workflow_mode")
    op.execute("DROP TYPE optimization_status")
    op.execute("DROP TYPE material_confirmation_status")
    op.execute("DROP TYPE file_purpose")
    op.execute("DROP TYPE file_lifecycle_status")
    op.execute("DROP TYPE book_workflow_mode")
