from agent1.tools import DEFAULT_ROW_LIMIT, _apply_default_limit


def test_result_limit_wraps_an_unlimited_query():
    wrapped = _apply_default_limit("SELECT * FROM orders;")
    assert wrapped == (
        "SELECT * FROM (SELECT * FROM orders) AS _agentic_sql_result "
        f"LIMIT {DEFAULT_ROW_LIMIT};"
    )


def test_result_limit_caps_a_model_supplied_large_limit():
    wrapped = _apply_default_limit("SELECT * FROM orders LIMIT 999999999;")
    assert "LIMIT 999999999) AS _agentic_sql_result" in wrapped
    assert wrapped.endswith(f"LIMIT {DEFAULT_ROW_LIMIT};")


def test_result_limit_wraps_ctes_without_rewriting_them():
    sql = "WITH x AS (SELECT * FROM orders) SELECT * FROM x;"
    wrapped = _apply_default_limit(sql)
    assert f"SELECT * FROM ({sql[:-1]}) AS _agentic_sql_result" in wrapped
    assert wrapped.endswith(f"LIMIT {DEFAULT_ROW_LIMIT};")
