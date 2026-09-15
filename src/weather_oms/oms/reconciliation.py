from dataclasses import dataclass

from weather_oms.oms.order_state import OrderState


@dataclass(frozen=True, slots=True)
class OrderSnapshot:
    client_order_id: str
    exchange_order_id: str | None
    state: OrderState
    count: int
    filled_count: int

    def __post_init__(self) -> None:
        if not self.client_order_id:
            raise ValueError(
                "client_order_id cannot be empty."
            )

        if self.count <= 0:
            raise ValueError("count must be positive.")

        if not 0 <= self.filled_count <= self.count:
            raise ValueError(
                "filled_count must be between zero "
                "and count."
            )

    @property
    def remaining_count(self) -> int:
        return self.count - self.filled_count


@dataclass(frozen=True, slots=True)
class Difference:
    client_order_id: str
    field: str
    internal: object
    exchange: object


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    differences: tuple[Difference, ...]

    @property
    def in_sync(self) -> bool:
        return not self.differences


def compare_orders(
    internal: tuple[OrderSnapshot, ...],
    exchange: tuple[OrderSnapshot, ...],
) -> ReconciliationReport:
    """Compare local and exchange records without changing either."""

    internal_by_id = _index_unique(
        internal,
        source="internal",
    )
    exchange_by_id = _index_unique(
        exchange,
        source="exchange",
    )

    differences: list[Difference] = []

    all_client_order_ids = sorted(
        set(internal_by_id) | set(exchange_by_id)
    )

    for client_order_id in all_client_order_ids:
        local = internal_by_id.get(client_order_id)
        remote = exchange_by_id.get(client_order_id)

        if local is None:
            differences.append(
                Difference(
                    client_order_id=client_order_id,
                    field="presence",
                    internal=False,
                    exchange=True,
                )
            )
            continue

        if remote is None:
            differences.append(
                Difference(
                    client_order_id=client_order_id,
                    field="presence",
                    internal=True,
                    exchange=False,
                )
            )
            continue

        fields = (
            (
                "exchange_order_id",
                local.exchange_order_id,
                remote.exchange_order_id,
            ),
            (
                "state",
                local.state,
                remote.state,
            ),
            (
                "count",
                local.count,
                remote.count,
            ),
            (
                "filled_count",
                local.filled_count,
                remote.filled_count,
            ),
            (
                "remaining_count",
                local.remaining_count,
                remote.remaining_count,
            ),
        )

        for field, internal_value, exchange_value in fields:
            if internal_value != exchange_value:
                differences.append(
                    Difference(
                        client_order_id=client_order_id,
                        field=field,
                        internal=internal_value,
                        exchange=exchange_value,
                    )
                )

    return ReconciliationReport(
        differences=tuple(differences)
    )


def _index_unique(
    orders: tuple[OrderSnapshot, ...],
    source: str,
) -> dict[str, OrderSnapshot]:
    indexed: dict[str, OrderSnapshot] = {}

    for order in orders:
        if order.client_order_id in indexed:
            raise ValueError(
                f"Duplicate {source} client_order_id: "
                f"{order.client_order_id}."
            )

        indexed[order.client_order_id] = order

    return indexed

