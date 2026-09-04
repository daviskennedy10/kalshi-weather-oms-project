from enum import StrEnum


class OrderState(StrEnum):
    # TODO(you): Challenge whether these states capture partial fills, cancellation,
    # ambiguous timeouts, rejection, and reconciliation. Then define legal transitions.
    DECIDED = "decided"
    SENT = "sent"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    RECORDED = "recorded"


def transition(current: OrderState, target: OrderState) -> OrderState:
    """YOUR CORE LOGIC: accept only transitions your state diagram permits."""
    # TODO(you): Write the transition table first, including terminal states and retry semantics.
    raise NotImplementedError("Design and implement the order state machine")

