from app.analyzer.rules.sql_conditions import extract_columns, suggest_create_index


def test_extract_columns_single_predicate():
    assert extract_columns("(status = 'pending'::text)") == ["status"]


def test_extract_columns_multiple_predicates():
    cols = extract_columns("(status = 'shipped'::text AND created_at > '2024-01-01'::date)")
    assert cols == ["status", "created_at"]


def test_extract_columns_deduplicates_and_preserves_order():
    cols = extract_columns("(a = 1 OR a = 2) AND b = 3")
    assert cols == ["a", "b"]


def test_extract_columns_skips_keywords_and_functions():
    cols = extract_columns("lower(name) = 'x' AND coalesce(y, 0) > 1")
    assert "lower" not in cols
    assert "coalesce" not in cols


def test_extract_columns_strips_leading_label():
    assert extract_columns("Index Cond: (id = 42)") == ["id"]


def test_extract_columns_none_or_empty():
    assert extract_columns(None) == []
    assert extract_columns("") == []


def test_suggest_create_index_builds_ddl():
    ddl = suggest_create_index("orders", "(status = 'pending'::text)")
    assert ddl is not None
    assert ddl.startswith("CREATE INDEX ON orders (status)")


def test_suggest_create_index_none_without_columns():
    assert suggest_create_index("orders", None) is None
    assert suggest_create_index("orders", "true") is None


def test_suggest_create_index_none_without_table():
    assert suggest_create_index("", "(status = 1)") is None
