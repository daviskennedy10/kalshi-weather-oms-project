import pytest

from weather_oms.oms.order_state import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    InvalidOrderTransition,
    OrderState,
    is_terminal,
    transition,
)

LEGAL_TRANSITIONS = [
    (current, target)
    for current, targets in ALLOWED_TRANSITIONS.items()
    for target in targets
]


ILLEGAL_TRANSITIONS = [
    (current, target)
    for current in OrderState
    for target in OrderState
    if (
        current != target
        and target not in ALLOWED_TRANSITIONS[current]
    )
]


@pytest.mark.parametrize(
    ("current", "target"),
    LEGAL_TRANSITIONS,
)
def test_accepts_every_legal_transition(
    current: OrderState,
    target: OrderState,
) -> None:
    assert transition(current, target) == target


@pytest.mark.parametrize(
    ("current", "target"),
    ILLEGAL_TRANSITIONS,
)
def test_rejects_every_illegal_transition(
    current: OrderState,
    target: OrderState,
) -> None:
    with pytest.raises(
        InvalidOrderTransition,
        match=(
            f"Cannot transition order from "
            f"{current.value} to {target.value}"
        ),
    ):
        transition(current, target)


@pytest.mark.parametrize("state", list(OrderState))
def test_repeated_state_is_idempotent(
    state: OrderState,
) -> None:
    assert transition(state, state) == state


@pytest.mark.parametrize(
    "state",
    list(TERMINAL_STATES),
)
def test_terminal_states_are_identified(
    state: OrderState,
) -> None:
    assert is_terminal(state) is True


@pytest.mark.parametrize(
    "state",
    [
        state
        for state in OrderState
        if state not in TERMINAL_STATES
    ],
)
def test_nonterminal_states_are_identified(
    state: OrderState,
) -> None:
    assert is_terminal(state) is False


def test_every_state_has_transition_rules() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(OrderState)


def test_unknown_order_must_reconcile_before_retry() -> None:
    assert ALLOWED_TRANSITIONS[OrderState.UNKNOWN] == frozenset(
        {
            OrderState.RECONCILING,
        }
    )

    with pytest.raises(InvalidOrderTransition):
        transition(
            OrderState.UNKNOWN,
            OrderState.SUBMITTING,
        )


@pytest.mark.parametrize(
    "terminal_state",
    list(TERMINAL_STATES),
)
def test_terminal_state_cannot_be_reopened(
    terminal_state: OrderState,
) -> None:
    with pytest.raises(InvalidOrderTransition):
        transition(
            terminal_state,
            OrderState.OPEN,
        )