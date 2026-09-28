"""Add account recovery, JWT revocation, and analytics metadata.

Revision ID: 20260720_0002
Revises: 20260720_0001
Create Date: 2026-07-20
"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_0002"
down_revision: str | None = "20260720_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())
    columns = {
        table: {item["name"]: item for item in inspector.get_columns(table)}
        for table in ("users", "datasets", "query_history")
    }

    def add_if_missing(table: str, column: sa.Column) -> None:
        if column.name not in columns[table]:
            op.add_column(table, column)
            columns[table][column.name] = {"name": column.name}

    add_if_missing(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    add_if_missing(
        "users",
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
    )
    add_if_missing(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    add_if_missing("datasets", sa.Column("file_type", sa.String(length=20), nullable=True))
    add_if_missing(
        "datasets",
        sa.Column("column_count", sa.Integer(), server_default="0", nullable=False),
    )
    add_if_missing("datasets", sa.Column("profile_json", sa.JSON(), nullable=True))
    add_if_missing(
        "datasets",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    add_if_missing(
        "datasets",
        sa.Column("last_queried_at", sa.DateTime(timezone=True), nullable=True),
    )

    if not columns["query_history"]["dataset_id"].get("nullable", False):
        op.alter_column("query_history", "dataset_id", existing_type=sa.Integer(), nullable=True)
    add_if_missing(
        "query_history", sa.Column("result_columns_json", sa.JSON(), nullable=True)
    )
    add_if_missing("query_history", sa.Column("result_json", sa.JSON(), nullable=True))
    add_if_missing(
        "query_history",
        sa.Column("row_count", sa.Integer(), server_default="0", nullable=False),
    )
    add_if_missing("query_history", sa.Column("quality_json", sa.JSON(), nullable=True))
    add_if_missing("query_history", sa.Column("quality_score", sa.Float(), nullable=True))
    add_if_missing(
        "query_history",
        sa.Column("rag_used", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    add_if_missing(
        "query_history",
        sa.Column("correction_used", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    add_if_missing("query_history", sa.Column("execution_ms", sa.Integer(), nullable=True))
    add_if_missing(
        "query_history",
        sa.Column(
            "status", sa.String(length=30), server_default="completed", nullable=False
        ),
    )
    add_if_missing(
        "query_history", sa.Column("report_path", sa.String(length=1000), nullable=True)
    )

    if "password_reset_tokens" not in table_names:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("request_ip", sa.String(length=45), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(op.get_bind())
    existing_indexes = {item["name"] for item in inspector.get_indexes("password_reset_tokens")}
    for name, fields, unique in (
        ("ix_password_reset_tokens_user_id", ["user_id"], False),
        ("ix_password_reset_tokens_token_hash", ["token_hash"], True),
        ("ix_password_reset_tokens_expires_at", ["expires_at"], False),
    ):
        if name not in existing_indexes:
            op.create_index(name, "password_reset_tokens", fields, unique=unique)


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

    op.drop_column("query_history", "report_path")
    op.drop_column("query_history", "status")
    op.drop_column("query_history", "execution_ms")
    op.drop_column("query_history", "correction_used")
    op.drop_column("query_history", "rag_used")
    op.drop_column("query_history", "quality_score")
    op.drop_column("query_history", "quality_json")
    op.drop_column("query_history", "row_count")
    op.drop_column("query_history", "result_json")
    op.drop_column("query_history", "result_columns_json")
    op.alter_column("query_history", "dataset_id", existing_type=sa.Integer(), nullable=False)

    op.drop_column("datasets", "last_queried_at")
    op.drop_column("datasets", "updated_at")
    op.drop_column("datasets", "profile_json")
    op.drop_column("datasets", "column_count")
    op.drop_column("datasets", "file_type")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "token_version")
    op.drop_column("users", "is_active")
