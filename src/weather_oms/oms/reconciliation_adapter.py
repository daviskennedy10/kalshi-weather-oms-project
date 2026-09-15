from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from weather_oms.oms.order_state import OrderState
from weather_oms.oms.reconciliation import OrderSnapshot
from weather_oms.storage.order_repository import StoredOrder


def stored_order_to_snapshot(
    order: StoredOrder,
) -> OrderSnapshot:
    """Convert one database order into a reconciliation snapshot."""

    return OrderSnapshot(
        client_order_id=order.client_order_id,
        exchange_order_id=order.exchange_order_id,
        state=order.state,
        count=order.count,
        filled_count=order.filled_count,
    )


def kalshi_order_to_snapshot(
    payload: Mapping[str, object],
) -> OrderSnapshot:
    """Convert one Kalshi order response into a snapshot."""

    client_order_id = _read_nonempty_string(
        payload,
        "client_order_id",
    )
    exchange_order_id = _read_nonempty_string(
        payload,
        "order_id",
    )
    status = _read_nonempty_string(
        payload,
        "status",
    ).lower()

    count = _read_whole_count(
        payload,
        "initial_count_fp",
    )
    filled_count = _read_whole_count(
        payload,
        "fill_count_fp",
    )
    remaining_count = _read_whole_count(
        payload,
        "remaining_count_fp",
    )

    if count <= 0:
        raise ValueError(
            "Kalshi initial_count_fp must be positive."
        )

    if filled_count + remaining_count != count:
        raise ValueError(
            "Kalshi fill and remaining counts do not "
            "equal the initial count."
        )

    state = _kalshi_state(
        status=status,
        count=count,
        filled_count=filled_count,
        remaining_count=remaining_count,
    )

    return OrderSnapshot(
        client_order_id=client_order_id,
        exchange_order_id=exchange_order_id,
        state=state,
        count=count,
        filled_count=filled_count,
    )


def _kalshi_state(
    status: str,
    count: int,
    filled_count: int,
    remaining_count: int,
) -> OrderState:
    if status == "resting":
        if remaining_count == 0:
            raise ValueError(
                "A resting Kalshi order must have "
                "remaining contracts."
            )

        if filled_count == 0:
            return OrderState.OPEN

        return OrderState.PARTIALLY_FILLED

    if status == "executed":
        if filled_count != count or remaining_count != 0:
            raise ValueError(
                "An executed Kalshi order must be "
                "fully filled."
            )

        return OrderState.FILLED

    if status == "canceled":
        return OrderState.CANCELLED

    raise ValueError(
        f"Unsupported Kalshi order status: {status!r}."
    )


def _read_nonempty_string(
    payload: Mapping[str, object],
    field: str,
) -> str:
    value = payload.get(field)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Kalshi order field {field!r} must be "
            "a non-empty string."
        )

    return value.strip()


def _read_whole_count(
    payload: Mapping[str, object],
    field: str,
) -> int:
    value = payload.get(field)

    if isinstance(value, bool):
        raise TypeError(
            f"Kalshi order field {field!r} must be "
            "a whole number."
        )

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(
            f"Kalshi order field {field!r} must be "
            "a whole number."
        ) from error

    if (
        not decimal_value.is_finite()
        or decimal_value < 0
        or decimal_value != decimal_value.to_integral_value()
    ):
        raise ValueError(
            f"Kalshi order field {field!r} must be "
            "a nonnegative whole number."
        )

    return int(decimal_value)