from datetime import datetime, timedelta

DEFAULT_MAXIMUM_QUOTE_AGE = timedelta(minutes=15)


def calculate_quote_age(
    retrieved_at: datetime,
    decision_at: datetime,
    maximum_age: timedelta = DEFAULT_MAXIMUM_QUOTE_AGE,
) -> timedelta:
    if retrieved_at.tzinfo is None:
        raise ValueError(
            "retrieved_at must include a timezone."
        )

    if decision_at.tzinfo is None:
        raise ValueError(
            "decision_at must include a timezone."
        )

    if maximum_age <= timedelta(0):
        raise ValueError(
            "maximum_age must be positive."
        )

    quote_age = decision_at - retrieved_at

    if quote_age < timedelta(0):
        raise ValueError(
            "Quote was retrieved after the decision time."
        )

    if quote_age > maximum_age:
        raise ValueError(
            "Kalshi quote is too old for this decision."
        )

    return quote_age