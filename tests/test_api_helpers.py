import pandas as pd

from api.main import assert_internal_table_name, build_profile, clean_columns, dynamic_quality, infer_dataframe_types


def test_clean_columns_are_unique_and_safe():
    assert clean_columns(["Sales $", "Sales $", "123 Region", "!!!"]) == [
        "sales", "sales_2", "col_123_region", "column_4"
    ]
    assert clean_columns(["select", "order"]) == ["col_select", "col_order"]


def test_conservative_date_inference():
    frame = pd.DataFrame({"order_date": ["2026-01-01", "2026-01-02"], "label": ["1", "2"]})
    inferred = infer_dataframe_types(frame)
    assert pd.api.types.is_datetime64_any_dtype(inferred["order_date"])
    assert not pd.api.types.is_datetime64_any_dtype(inferred["label"])


def test_dataset_profile_is_bounded_and_json_ready():
    frame = pd.DataFrame({"sales": [10.0, None, 30.0], "region": ["North", "South", "North"]})
    profile = build_profile(frame)
    assert profile["row_count"] == 3
    assert profile["column_count"] == 2
    assert profile["columns"][0]["null_count"] == 1
    assert len(profile["sample_rows"]) == 3


def test_internal_table_name_policy():
    assert_internal_table_name("dataset_42_abcdef1234")
    for unsafe in ("users", "dataset_42_bad", 'dataset_1_x\"; DROP TABLE users;--'):
        try:
            assert_internal_table_name(unsafe)
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"Unsafe table name accepted: {unsafe}")


def test_dynamic_quality_uses_selected_table_allowlist():
    allowed = dynamic_quality(
        "SELECT region, SUM(sales) AS sales FROM dataset_42_abcdef1234 GROUP BY region;",
        "dataset_42_abcdef1234",
        ["region", "sales"],
    )
    denied = dynamic_quality("SELECT * FROM users;", "dataset_42_abcdef1234", ["id"])
    assert allowed["passed"] is True
    assert denied["passed"] is False
