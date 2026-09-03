from app.analyzer.fingerprint import fingerprint_query


def test_fingerprint_none_for_empty_query():
    assert fingerprint_query(None) is None
    assert fingerprint_query("   ") is None


def test_fingerprint_is_stable_for_identical_query():
    q = "SELECT * FROM orders WHERE id = 42"
    assert fingerprint_query(q) == fingerprint_query(q)


def test_fingerprint_ignores_literal_values():
    a = fingerprint_query("SELECT * FROM orders WHERE id = 42")
    b = fingerprint_query("SELECT * FROM orders WHERE id = 99999")
    assert a == b


def test_fingerprint_ignores_string_literals_and_whitespace():
    a = fingerprint_query("SELECT * FROM orders WHERE status = 'shipped'")
    b = fingerprint_query("select   *  from orders where status = 'pending'")
    assert a == b


def test_fingerprint_differs_for_different_query_shape():
    a = fingerprint_query("SELECT * FROM orders WHERE id = 42")
    b = fingerprint_query("SELECT * FROM customers WHERE id = 42")
    assert a != b
