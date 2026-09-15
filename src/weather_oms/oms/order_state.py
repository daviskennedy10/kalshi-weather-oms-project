from enum import StrEnum


class OrderState(StrEnum):
    DECIDED = "decided"
    SUBMITTING = "submitting"
    UNKNOWN = "unknown"
    RECONCILING = "reconciling"
    RETRY_READY = "retry_ready"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    CANCEL_PENDING = "cancel_pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class InvalidOrderTransition(ValueError):
    """Raised when an unsafe order-state change is attempted."""


TERMINAL_STATES = frozenset(
    {
        OrderState.FILLED,
        OrderState.CANCELLED,
        OrderState.REJECTED,
        OrderState.EXPIRED,
    }
)


ALLOWED_TRANSITIONS: dict[
    OrderState,
    frozenset[OrderState],
] = {
    OrderState.DECIDED: frozenset(
        {
            OrderState.SUBMITTING,
        }
    ),
    OrderState.SUBMITTING: frozenset(
        {
            OrderState.UNKNOWN,
            OrderState.OPEN,
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.REJECTED,
        }
    ),
    OrderState.UNKNOWN: frozenset(
        {
            OrderState.RECONCILING,
        }
    ),
    OrderState.RECONCILING: frozenset(
        {
            OrderState.RETRY_READY,
            OrderState.OPEN,
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.REJECTED,
            OrderState.EXPIRED,
        }
    ),
    OrderState.RETRY_READY: frozenset(
        {
            OrderState.SUBMITTING,
        }
    ),
    OrderState.OPEN: frozenset(
        {
            OrderState.PARTIALLY_FILLED,
            OrderState.CANCEL_PENDING,
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.EXPIRED,
            OrderState.RECONCILING,
        }
    ),
    OrderState.PARTIALLY_FILLED: frozenset(
        {
            OrderState.CANCEL_PENDING,
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.EXPIRED,
            OrderState.RECONCILING,
        }
    ),
    OrderState.CANCEL_PENDING: frozenset(
        {
            OrderState.OPEN,
            OrderState.PARTIALLY_FILLED,
            OrderState.FILLED,
            OrderState.CANCELLED,
            OrderState.EXPIRED,
            OrderState.RECONCILING,
        }
    ),
    OrderState.FILLED: frozenset(),
    OrderState.CANCELLED: frozenset(),
    OrderState.REJECTED: frozenset(),
    OrderState.EXPIRED: frozenset(),
}


def is_terminal(state: OrderState) -> bool:
    return state in TERMINAL_STATES


def transition(
    current: OrderState,
    target: OrderState,
) -> OrderState:
    """Return the target state only when the change is safe."""

    # Repeated exchange messages are harmless.
    if current == target:
        return current

    allowed_targets = ALLOWED_TRANSITIONS[current]

    if target not in allowed_targets:
        raise InvalidOrderTransition(
            f"Cannot transition order from "
            f"{current.value} to {target.value}."
        )

    return target