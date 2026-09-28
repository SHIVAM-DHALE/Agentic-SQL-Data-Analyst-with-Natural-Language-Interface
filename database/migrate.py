"""Safely bootstrap Alembic for new and pre-Alembic project databases."""
from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from database.user_models import engine

INITIAL_REVISION = "20260720_0001"
HEAD_REVISION = "20260720_0002"
CORE_TABLES = {"users", "datasets", "query_history"}


def upgrade_database() -> None:
    config = Config("alembic.ini")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "alembic_version" in tables:
        command.upgrade(config, "head")
        return

    existing_core = CORE_TABLES & tables
    if not existing_core:
        command.upgrade(config, "head")
        return

    if existing_core != CORE_TABLES:
        missing = ", ".join(sorted(CORE_TABLES - existing_core))
        raise RuntimeError(
            "A partial multi-user schema was found. Back up the database and "
            f"repair the missing tables before migration: {missing}"
        )

    user_columns = {item["name"] for item in inspector.get_columns("users")}
    dataset_columns = {item["name"] for item in inspector.get_columns("datasets")}
    enhanced = {"token_version", "is_active", "updated_at"} <= user_columns and {
        "profile_json", "column_count", "last_queried_at"
    } <= dataset_columns and "password_reset_tokens" in tables

    if enhanced:
        command.stamp(config, HEAD_REVISION)
        return

    partial_enhancement = bool(
        ({"token_version", "is_active", "updated_at"} & user_columns)
        or ({"profile_json", "column_count", "last_queried_at"} & dataset_columns)
    )
    if partial_enhancement:
        raise RuntimeError(
            "A partially upgraded schema was found. Back up the database and "
            "review the 20260720_0002 migration before retrying."
        )

    # The immediately previous release created these tables with create_all().
    # Mark that known schema as the initial revision, then apply only additions.
    command.stamp(config, INITIAL_REVISION)
    command.upgrade(config, "head")


if __name__ == "__main__":
    upgrade_database()
    print("Database schema is at the latest revision.")
