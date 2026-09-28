"""Validate generated PostgreSQL before it reaches the database.

The validator deliberately supports a small, read-only SQL surface.  It is not
intended to be a complete PostgreSQL parser; unsupported or ambiguous syntax is
rejected instead of guessed.  Database execution must still use a restricted
role and a read-only transaction (see :mod:`agent1.tools`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence


DEFAULT_ALLOWED_TABLES = frozenset(
    {"customers", "products", "orders", "order_items"}
)

# Keywords are checked only outside string literals.  INTO is included because
# PostgreSQL's SELECT ... INTO form creates a table even though it begins SELECT.
BLOCKED_SQL_KEYWORDS = frozenset(
    {
        "ABORT",
        "ALTER",
        "ANALYZE",
        "BEGIN",
        "CALL",
        "CHECKPOINT",
        "CLOSE",
        "CLUSTER",
        "COMMENT",
        "COMMIT",
        "COPY",
        "CREATE",
        "DEALLOCATE",
        "DECLARE",
        "DELETE",
        "DISCARD",
        "DO",
        "DROP",
        "EXECUTE",
        "GRANT",
        "IMPORT",
        "INSERT",
        "INTO",
        "LISTEN",
        "LOAD",
        "LOCK",
        "MERGE",
        "MOVE",
        "NOTIFY",
        "PREPARE",
        "REASSIGN",
        "REFRESH",
        "REINDEX",
        "RELEASE",
        "REPLACE",
        "RESET",
        "REVOKE",
        "ROLLBACK",
        "SAVEPOINT",
        "SECURITY",
        "SET",
        "SHOW",
        "START",
        "TABLE",
        "TRUNCATE",
        "UNLISTEN",
        "UPDATE",
        "VACUUM",
    }
)

SYSTEM_SCHEMAS = frozenset(
    {
        "information_schema",
        "pg_catalog",
        "pg_temp",
        "pg_toast",
        "pg_toast_temp",
    }
)
UNSAFE_FUNCTION_SCHEMAS = frozenset(
    {
        "aws_lambda",
        "aws_s3",
        "dblink",
        "http",
        "net",
    }
)
UNSAFE_FUNCTION_NAMES = frozenset(
    {
        "cursor_to_xml",
        "current_setting",
        "currval",
        "database_to_xml",
        "database_to_xml_and_xmlschema",
        "http",
        "lo_export",
        "lo_import",
        "lastval",
        "nextval",
        "pg_cancel_backend",
        "pg_create_restore_point",
        "pg_logdir_ls",
        "pg_notify",
        "pg_promote",
        "pg_reload_conf",
        "pg_rotate_logfile",
        "pg_sleep",
        "pg_sleep_for",
        "pg_sleep_until",
        "pg_stat_file",
        "pg_switch_wal",
        "pg_switch_xlog",
        "pg_terminate_backend",
        "query_to_xml",
        "query_to_xml_and_xmlschema",
        "schema_to_xml",
        "schema_to_xml_and_xmlschema",
        "set_config",
        "setval",
        "sys_eval",
        "sys_exec",
        "table_to_xml",
        "table_to_xml_and_xmlschema",
    }
)

_UNSAFE_FUNCTION_PREFIXES = (
    "curl_",
    "dblink",
    "http_",
    "lo_",
    "pg_",
)
_SYSTEM_SCHEMA_PREFIXES = ("pg_temp_", "pg_toast_temp_")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_DOLLAR_QUOTE_RE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")
_FROM_TERMINATORS = frozenset(
    {
        "EXCEPT",
        "FETCH",
        "FOR",
        "GROUP",
        "HAVING",
        "INTERSECT",
        "LIMIT",
        "OFFSET",
        "ORDER",
        "QUALIFY",
        "RETURNING",
        "UNION",
        "WHERE",
        "WINDOW",
    }
)


class _SQLValidationError(ValueError):
    """Internal exception converted to the public ``(bool, message)`` API."""


@dataclass(frozen=True)
class _Token:
    value: str
    kind: str
    depth: int
    position: int

    @property
    def upper(self) -> str:
        return self.value.upper()


@dataclass(frozen=True)
class _CTEDefinition:
    name: str
    body_start: int
    body_end: int


@dataclass(frozen=True)
class _WithScope:
    definitions: tuple[_CTEDefinition, ...]
    main_start: int
    scope_end: int
    recursive: bool


def _is_system_schema(name: str) -> bool:
    lowered = name.casefold()
    return lowered in SYSTEM_SCHEMAS or lowered.startswith(_SYSTEM_SCHEMA_PREFIXES)


def _tokenize(sql: str) -> tuple[list[_Token], list[int]]:
    """Tokenize the safe subset while detecting comments and ambiguous quotes."""

    tokens: list[_Token] = []
    semicolons: list[int] = []
    depth = 0
    index = 0
    length = len(sql)

    while index < length:
        char = sql[index]

        if char.isspace():
            index += 1
            continue

        if ord(char) < 32:
            raise _SQLValidationError("SQL contains an unsupported control character.")

        if sql.startswith("--", index) or sql.startswith("/*", index) or sql.startswith("*/", index):
            raise _SQLValidationError("SQL comments are not allowed.")

        if char == "'":
            start = index
            is_escape_string = (
                index > 0
                and sql[index - 1] in {"e", "E"}
                and (index == 1 or not (sql[index - 2].isalnum() or sql[index - 2] in {"_", "$"}))
            )
            index += 1
            while index < length:
                if sql[index] == "'":
                    if index + 1 < length and sql[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    break
                if sql[index] == "\\":
                    if not is_escape_string:
                        raise _SQLValidationError(
                            "Backslash escapes in standard SQL strings are not supported."
                        )
                    if index + 1 >= length:
                        raise _SQLValidationError("SQL has an unterminated string literal.")
                    index += 2
                    continue
                index += 1
            else:
                raise _SQLValidationError("SQL has an unterminated string literal.")

            tokens.append(_Token("<string>", "string", depth, start))
            continue

        if char == '"':
            raise _SQLValidationError(
                "Quoted SQL identifiers are not supported; use sanitized unquoted identifiers."
            )

        if char == "`":
            raise _SQLValidationError("Backtick-quoted identifiers are not valid PostgreSQL here.")

        if char == "$":
            dollar_match = _DOLLAR_QUOTE_RE.match(sql, index)
            if dollar_match:
                raise _SQLValidationError("Dollar-quoted SQL strings are not supported.")
            raise _SQLValidationError("SQL parameters using '$' are not supported.")

        if char == "(":
            tokens.append(_Token(char, "symbol", depth, index))
            depth += 1
            index += 1
            continue

        if char == ")":
            if depth == 0:
                raise _SQLValidationError("SQL has unbalanced parentheses.")
            depth -= 1
            tokens.append(_Token(char, "symbol", depth, index))
            index += 1
            continue

        if char == ";":
            semicolons.append(index)
            tokens.append(_Token(char, "symbol", depth, index))
            index += 1
            continue

        if char.isascii() and (char.isalpha() or char == "_"):
            start = index
            index += 1
            while index < length and sql[index].isascii() and (
                sql[index].isalnum() or sql[index] in {"_", "$"}
            ):
                index += 1
            tokens.append(_Token(sql[start:index], "word", depth, start))
            continue

        if char.isdigit():
            start = index
            index += 1
            while index < length and (
                sql[index].isdigit() or sql[index] in {".", "e", "E", "+", "-"}
            ):
                index += 1
            tokens.append(_Token(sql[start:index], "number", depth, start))
            continue

        if not char.isascii():
            raise _SQLValidationError(
                "Non-ASCII SQL identifiers are not supported; use sanitized identifiers."
            )

        tokens.append(_Token(char, "symbol", depth, index))
        index += 1

    if depth:
        raise _SQLValidationError("SQL has unbalanced parentheses.")

    return tokens, semicolons


def _find_matching_close(tokens: Sequence[_Token], open_index: int) -> int:
    if tokens[open_index].value != "(":
        raise _SQLValidationError("Expected an opening parenthesis.")

    base_depth = tokens[open_index].depth
    for index in range(open_index + 1, len(tokens)):
        token = tokens[index]
        if token.value == ")" and token.depth == base_depth:
            return index
    raise _SQLValidationError("SQL has unbalanced parentheses.")


def _parse_with_clause(
    tokens: Sequence[_Token], with_index: int, scope_end: int
) -> _WithScope:
    """Parse CTE names and body ranges for one WITH query."""

    base_depth = tokens[with_index].depth
    index = with_index + 1
    recursive = False

    if index < scope_end and tokens[index].depth == base_depth and tokens[index].upper == "RECURSIVE":
        recursive = True
        index += 1

    definitions: list[_CTEDefinition] = []
    while index < scope_end:
        name_token = tokens[index]
        if name_token.depth != base_depth or name_token.kind != "word":
            raise _SQLValidationError("Malformed WITH clause.")
        cte_name = name_token.value.casefold()
        index += 1

        # Optional CTE output-column list: name(col_a, col_b) AS (...)
        if index < scope_end and tokens[index].value == "(" and tokens[index].depth == base_depth:
            index = _find_matching_close(tokens, index) + 1

        if not (
            index < scope_end
            and tokens[index].depth == base_depth
            and tokens[index].upper == "AS"
        ):
            raise _SQLValidationError("Malformed WITH clause: expected AS.")
        index += 1

        if index < scope_end and tokens[index].depth == base_depth and tokens[index].upper == "NOT":
            index += 1
            if not (
                index < scope_end
                and tokens[index].depth == base_depth
                and tokens[index].upper == "MATERIALIZED"
            ):
                raise _SQLValidationError("Malformed WITH clause after NOT.")
            index += 1
        elif index < scope_end and tokens[index].depth == base_depth and tokens[index].upper == "MATERIALIZED":
            index += 1

        if not (
            index < scope_end
            and tokens[index].value == "("
            and tokens[index].depth == base_depth
        ):
            raise _SQLValidationError("Malformed WITH clause: expected a query body.")

        close_index = _find_matching_close(tokens, index)
        definitions.append(
            _CTEDefinition(
                name=cte_name,
                body_start=index + 1,
                body_end=close_index,
            )
        )
        index = close_index + 1

        if (
            index < scope_end
            and tokens[index].value == ","
            and tokens[index].depth == base_depth
        ):
            index += 1
            continue
        break

    if not definitions or index >= scope_end:
        raise _SQLValidationError("Malformed WITH clause.")

    return _WithScope(tuple(definitions), index, scope_end, recursive)


def _is_query_start(tokens: Sequence[_Token], index: int) -> bool:
    if index == 0:
        return True
    token = tokens[index]
    previous = tokens[index - 1]
    return previous.value == "(" and previous.depth == token.depth - 1


def _scope_end_for_depth(tokens: Sequence[_Token], start: int) -> int:
    depth = tokens[start].depth
    for index in range(start + 1, len(tokens)):
        if tokens[index].depth < depth:
            return index
    return len(tokens)


def _with_scopes(tokens: Sequence[_Token]) -> list[_WithScope]:
    scopes: list[_WithScope] = []
    for index, token in enumerate(tokens):
        if token.kind == "word" and token.upper == "WITH" and _is_query_start(tokens, index):
            scope_end = _scope_end_for_depth(tokens, index)
            scopes.append(_parse_with_clause(tokens, index, scope_end))
    return scopes


def _cte_is_visible(
    name: str, reference_index: int, scopes: Sequence[_WithScope]
) -> bool:
    """Return whether *name* resolves to a CTE at this lexical position."""

    name = name.casefold()
    for scope in scopes:
        definitions = scope.definitions
        if scope.main_start <= reference_index < scope.scope_end:
            if any(item.name == name for item in definitions):
                return True

        for definition_index, definition in enumerate(definitions):
            if definition.body_start <= reference_index < definition.body_end:
                # A recursive CTE can see itself.  Previous CTEs are visible in
                # every CTE body; later CTEs are intentionally not treated as
                # visible because PostgreSQL forward references are invalid.
                visible_count = definition_index + (1 if scope.recursive else 0)
                if any(
                    item.name == name
                    for item in definitions[:visible_count]
                ):
                    return True
    return False


def _read_qualified_name(
    tokens: Sequence[_Token], start: int
) -> tuple[list[str], int]:
    if start >= len(tokens) or tokens[start].kind != "word":
        return [], start

    depth = tokens[start].depth
    parts = [tokens[start].value.casefold()]
    index = start + 1
    while (
        index + 1 < len(tokens)
        and tokens[index].value == "."
        and tokens[index].depth == depth
        and tokens[index + 1].kind == "word"
        and tokens[index + 1].depth == depth
    ):
        parts.append(tokens[index + 1].value.casefold())
        index += 2
    return parts, index


def _has_query_select_before(tokens: Sequence[_Token], from_index: int) -> bool:
    """Avoid mistaking EXTRACT(... FROM value) for a query FROM clause."""

    depth = tokens[from_index].depth
    for index in range(from_index - 1, -1, -1):
        token = tokens[index]
        if token.depth < depth or token.value == ";":
            break
        if token.depth == depth and token.kind == "word" and token.upper == "SELECT":
            return True
    return False


def _referenced_tables_from_tokens(
    tokens: Sequence[_Token], scopes: Sequence[_WithScope]
) -> set[str]:
    targets: set[str] = set()

    for from_index, from_token in enumerate(tokens):
        if not (
            from_token.kind == "word"
            and from_token.upper == "FROM"
            and _has_query_select_before(tokens, from_index)
        ):
            continue

        base_depth = from_token.depth
        index = from_index + 1
        expect_source = True

        while index < len(tokens):
            token = tokens[index]
            if token.depth < base_depth or token.value == ";":
                break
            if token.depth > base_depth:
                index += 1
                continue

            upper = token.upper
            if token.kind == "word" and upper in _FROM_TERMINATORS:
                break

            if not expect_source:
                if token.value == ",":
                    expect_source = True
                elif token.kind == "word" and upper == "JOIN":
                    expect_source = True
                index += 1
                continue

            if token.kind == "word" and upper in {"LATERAL", "ONLY"}:
                if upper == "ONLY" and (
                    index + 1 < len(tokens) and tokens[index + 1].value == "("
                ):
                    raise _SQLValidationError(
                        "Parenthesized ONLY table references are not supported."
                    )
                index += 1
                continue

            if token.value == "(":
                close_index = _find_matching_close(tokens, index)
                first_inner = tokens[index + 1] if index + 1 < close_index else None
                if not (
                    first_inner
                    and first_inner.kind == "word"
                    and first_inner.upper in {"SELECT", "WITH", "VALUES"}
                ):
                    # PostgreSQL also permits parenthesized joined tables and
                    # ONLY(table).  Reject those less common forms instead of
                    # skipping physical relation names inside them.
                    raise _SQLValidationError(
                        "Unsupported parenthesized FROM/JOIN target."
                    )
                # A normal parenthesized subquery/VALUES relation is analyzed
                # independently by the outer token scan.
                index = close_index + 1
                expect_source = False
                continue

            parts, next_index = _read_qualified_name(tokens, index)
            if not parts:
                raise _SQLValidationError("Unsupported FROM/JOIN target syntax.")

            # A name followed by '(' is a set-returning function, not a table.
            if (
                next_index < len(tokens)
                and tokens[next_index].value == "("
                and tokens[next_index].depth == base_depth
            ):
                index = _find_matching_close(tokens, next_index) + 1
                expect_source = False
                continue

            canonical = ".".join(parts)
            if len(parts) > 1 or not _cte_is_visible(parts[0], index, scopes):
                targets.add(canonical)
            index = next_index
            expect_source = False

    return targets


def _referenced_tables(sql: str) -> set[str]:
    """Extract physical FROM/JOIN targets; visible CTE aliases are excluded."""

    tokens, semicolons = _tokenize(sql)
    if semicolons and (len(semicolons) > 1 or tokens[-1].value != ";"):
        raise _SQLValidationError("Multiple SQL statements are not allowed.")
    if tokens and tokens[-1].value == ";":
        tokens = tokens[:-1]
    return _referenced_tables_from_tokens(tokens, _with_scopes(tokens))


def _normalize_allowed_tables(allowed_tables: Optional[Iterable[str]]) -> set[str]:
    values: Iterable[str]
    if allowed_tables is None:
        values = DEFAULT_ALLOWED_TABLES
    elif isinstance(allowed_tables, str):
        values = (allowed_tables,)
    else:
        values = allowed_tables

    normalized: set[str] = set()
    for table in values:
        if not isinstance(table, str) or not table.strip():
            raise _SQLValidationError("The allowed table list contains an invalid identifier.")
        parts = table.strip().split(".")
        if len(parts) > 2 or any(not _IDENTIFIER_RE.fullmatch(part) for part in parts):
            raise _SQLValidationError(
                f"Allowed table identifier '{table}' is not a safe unquoted identifier."
            )
        canonical = ".".join(part.casefold() for part in parts)
        if _is_system_schema(parts[0]) or parts[-1].casefold().startswith("pg_"):
            raise _SQLValidationError("System tables cannot be added to the allowed table list.")
        normalized.add(canonical)
    return normalized


def _validate_function_calls(tokens: Sequence[_Token]) -> None:
    for index, token in enumerate(tokens):
        if token.kind != "word":
            continue
        parts, next_index = _read_qualified_name(tokens, index)
        if not parts or next_index >= len(tokens) or tokens[next_index].value != "(":
            continue

        base_name = parts[-1]
        if len(parts) > 1 and parts[0] in UNSAFE_FUNCTION_SCHEMAS:
            raise _SQLValidationError(
                f"Calls to functions in schema '{parts[0]}' are not allowed."
            )
        if base_name in UNSAFE_FUNCTION_NAMES or base_name.startswith(_UNSAFE_FUNCTION_PREFIXES):
            raise _SQLValidationError(f"Unsafe SQL function detected: {base_name}.")


def _validate_system_schema_references(tokens: Sequence[_Token]) -> None:
    for index, token in enumerate(tokens[:-1]):
        if (
            token.kind == "word"
            and _is_system_schema(token.value)
            and tokens[index + 1].value == "."
        ):
            raise _SQLValidationError(
                f"Access to system schema '{token.value.casefold()}' is not allowed."
            )


def _validate_statement_shape(tokens: Sequence[_Token]) -> None:
    if not tokens or tokens[0].kind != "word":
        raise _SQLValidationError("Only SELECT or WITH ... SELECT queries are allowed.")

    first = tokens[0].upper
    if first == "SELECT":
        return
    if first != "WITH":
        raise _SQLValidationError("Only SELECT or WITH ... SELECT queries are allowed.")

    scope = _parse_with_clause(tokens, 0, len(tokens))
    main = tokens[scope.main_start]
    if main.depth != 0 or main.kind != "word" or main.upper != "SELECT":
        raise _SQLValidationError("WITH queries must end in a SELECT statement.")


def validate_sql(sql: str, allowed_tables: Optional[Iterable[str]] = None):
    """Return ``(is_valid, message)`` for a generated SQL statement.

    ``allowed_tables=None`` preserves demo mode.  An explicitly empty iterable
    means no physical tables are allowed; it never falls back to demo tables.
    Schema-qualified references are permitted only when that exact qualified
    name is also present in ``allowed_tables``.
    """

    try:
        if not isinstance(sql, str) or not sql.strip():
            raise _SQLValidationError("SQL is empty.")
        if len(sql) > 100_000:
            raise _SQLValidationError("SQL exceeds the maximum supported length.")

        tokens, semicolons = _tokenize(sql.strip())
        if not tokens:
            raise _SQLValidationError("SQL is empty.")
        if len(semicolons) > 1 or (semicolons and tokens[-1].value != ";"):
            raise _SQLValidationError("Multiple SQL statements are not allowed.")
        if tokens[-1].value == ";":
            tokens = tokens[:-1]
        if not tokens:
            raise _SQLValidationError("SQL is empty.")

        _validate_statement_shape(tokens)

        for token in tokens:
            if token.kind == "word" and token.upper in BLOCKED_SQL_KEYWORDS:
                raise _SQLValidationError(
                    f"Blocked SQL keyword detected: {token.upper}."
                )

        # SELECT ... FOR SHARE is a row-locking statement.  FOR UPDATE is
        # already rejected by the UPDATE keyword check above.
        words = [token.upper for token in tokens if token.kind == "word"]
        if any(
            words[index] == "FOR"
            and words[index + 1] in {"SHARE", "KEY"}
            for index in range(len(words) - 1)
        ):
            raise _SQLValidationError("Row-locking SELECT queries are not allowed.")

        _validate_system_schema_references(tokens)
        _validate_function_calls(tokens)

        allowed = _normalize_allowed_tables(allowed_tables)
        scopes = _with_scopes(tokens)
        for table in _referenced_tables_from_tokens(tokens, scopes):
            parts = table.split(".")
            if _is_system_schema(parts[0]) or parts[-1].startswith("pg_"):
                raise _SQLValidationError(
                    f"Access to system table '{table}' is not allowed."
                )
            if table not in allowed:
                raise _SQLValidationError(
                    f"Table '{table}' is not in the allowed table list."
                )

        return True, "SQL is valid."
    except _SQLValidationError as exc:
        return False, str(exc)


if __name__ == "__main__":
    examples = [
        "SELECT * FROM orders;",
        "DELETE FROM orders;",
        "SELECT COUNT(*) FROM orders",
        "SELECT * FROM orders;;",
        "SELECT * FROM orders; DROP TABLE orders;",
        "SELECT * FROM orders -- comment",
    ]
    for example in examples:
        print(validate_sql(example))
