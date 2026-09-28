import pytest

import database.migrate as migrate


class Inspector:
    def __init__(self, tables, columns=None):
        self.tables = tables
        self.columns = columns or {}

    def get_table_names(self):
        return list(self.tables)

    def get_columns(self, table):
        return [{"name": name} for name in self.columns.get(table, set())]


def capture(monkeypatch, inspector):
    calls = []
    monkeypatch.setattr(migrate, "inspect", lambda _: inspector)
    monkeypatch.setattr(migrate.command, "upgrade", lambda config, revision: calls.append(("upgrade", revision)))
    monkeypatch.setattr(migrate.command, "stamp", lambda config, revision: calls.append(("stamp", revision)))
    migrate.upgrade_database()
    return calls


def test_new_database_runs_all_migrations(monkeypatch):
    assert capture(monkeypatch, Inspector(set())) == [("upgrade", "head")]


def test_legacy_create_all_database_is_safely_baselined(monkeypatch):
    calls = capture(monkeypatch, Inspector(migrate.CORE_TABLES))
    assert calls == [("stamp", migrate.INITIAL_REVISION), ("upgrade", "head")]


def test_legacy_core_with_create_all_reset_table_is_safely_baselined(monkeypatch):
    calls = capture(monkeypatch, Inspector(migrate.CORE_TABLES | {"password_reset_tokens"}))
    assert calls == [("stamp", migrate.INITIAL_REVISION), ("upgrade", "head")]


def test_enhanced_unversioned_database_is_stamped_at_head(monkeypatch):
    tables = migrate.CORE_TABLES | {"password_reset_tokens"}
    columns = {
        "users": {"token_version", "is_active", "updated_at"},
        "datasets": {"profile_json", "column_count", "last_queried_at"},
    }
    assert capture(monkeypatch, Inspector(tables, columns)) == [("stamp", migrate.HEAD_REVISION)]


def test_partial_schema_requires_manual_review(monkeypatch):
    monkeypatch.setattr(migrate, "inspect", lambda _: Inspector({"users"}))
    with pytest.raises(RuntimeError, match="partial multi-user schema"):
        migrate.upgrade_database()
