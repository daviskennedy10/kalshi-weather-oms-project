from weather_oms.oms.reconciliation import compare_orders


def test_reconciliation_finds_mismatch_and_missing_order() -> None:
    internal = [
        {"client_order_id": "a", "status": "open", "filled_count": 0, "remaining_count": 2},
        {"client_order_id": "b", "status": "sent", "filled_count": 0, "remaining_count": 1},
    ]
    exchange = [
        {"client_order_id": "a", "status": "filled", "filled_count": 2, "remaining_count": 0}
    ]
    differences = compare_orders(internal, exchange)
    assert {(d.client_order_id, d.field) for d in differences} == {
        ("a", "status"), ("a", "filled_count"), ("a", "remaining_count"), ("b", "presence")
    }

