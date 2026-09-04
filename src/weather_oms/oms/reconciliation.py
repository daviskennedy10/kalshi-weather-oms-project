from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Difference:
    client_order_id: str
    field: str
    internal: object
    exchange: object


def compare_orders(internal: list[dict[str, object]], exchange: list[dict[str, object]]) -> list[Difference]:
    """Pure comparison layer; remediation stays explicit and separately auditable."""
    exchange_by_id = {str(row["client_order_id"]): row for row in exchange}
    differences: list[Difference] = []
    for local in internal:
        key = str(local["client_order_id"])
        remote = exchange_by_id.get(key)
        if remote is None:
            differences.append(Difference(key, "presence", True, False))
            continue
        for field in ("status", "filled_count", "remaining_count"):
            if local.get(field) != remote.get(field):
                differences.append(Difference(key, field, local.get(field), remote.get(field)))
    return differences

