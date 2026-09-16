"use strict";

const form = document.querySelector("#date-form");
const dateInput = document.querySelector("#target-date");
const message = document.querySelector("#message");
const dashboard = document.querySelector("#dashboard");
const submitButton = form.querySelector("button");

dateInput.value = new Date().toLocaleDateString(
    "en-CA"
);

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const targetDate = dateInput.value;

    if (!targetDate) {
        showError("Choose a target date.");
        return;
    }

    setLoading(true);

    try {
        const response = await fetch(
            `/api/performance/${targetDate}`
        );

        if (!response.ok) {
            throw new Error(
                `The server returned ${response.status}.`
            );
        }

        const report = await response.json();

        renderReport(report);
        message.classList.add("hidden");
        dashboard.classList.remove("hidden");
    } catch (error) {
        dashboard.classList.add("hidden");

        const detail = (
            error instanceof Error
                ? error.message
                : "Unknown error."
        );

        showError(`Could not load the report. ${detail}`);
    } finally {
        setLoading(false);
    }
});

function renderReport(report) {
    const positions = report.positions;
    const profit = report.profit;
    const latency = report.latency;
    const probability = report.probability;

    setText(
        "total-pnl",
        formatSignedDollars(profit.total_pnl_dollars)
    );
    setPnlColor(profit.total_pnl_dollars);

    setText(
        "return-on-cost",
        `Return on cost: ${
            formatPercentage(profit.return_on_cost)
        }`
    );

    setText("total-positions", positions.total);
    setText(
        "position-status",
        `${positions.open} open · ${positions.settled} settled`
    );
    setText(
        "win-rate",
        formatPercentage(positions.win_rate)
    );
    setText(
        "win-record",
        `${positions.wins} wins · ${positions.losses} losses`
    );

    setText(
        "mean-latency",
        formatMilliseconds(latency.mean_ms)
    );
    setText(
        "latency-samples",
        `${latency.samples} samples`
    );

    setText(
        "total-cost",
        formatDollars(profit.total_cost_dollars)
    );
    setText(
        "total-payout",
        formatDollars(profit.total_payout_dollars)
    );
    setText(
        "average-pnl",
        formatOptionalSignedDollars(
            profit.average_pnl_dollars
        )
    );
    setText(
        "maximum-drawdown",
        formatDollars(
            profit.maximum_drawdown_dollars
        )
    );

    setText(
        "minimum-latency",
        formatMilliseconds(latency.minimum_ms)
    );
    setText(
        "detail-mean-latency",
        formatMilliseconds(latency.mean_ms)
    );
    setText(
        "p95-latency",
        formatMilliseconds(
            latency.percentile_95_ms
        )
    );
    setText(
        "maximum-latency",
        formatMilliseconds(latency.maximum_ms)
    );

    if (probability === null) {
        setText("brier-score", "N/A");
        setText("log-loss", "N/A");
        setText("calibration-error", "N/A");
        setText("probability-samples", "0");
        return;
    }

    setText(
        "brier-score",
        formatScore(probability.brier_score)
    );
    setText(
        "log-loss",
        formatScore(probability.log_loss)
    );
    setText(
        "calibration-error",
        formatPercentage(
            probability.calibration_error
        )
    );
    setText(
        "probability-samples",
        probability.samples
    );
}

function setLoading(isLoading) {
    submitButton.disabled = isLoading;
    submitButton.textContent = (
        isLoading ? "Loading..." : "Load report"
    );

    if (isLoading) {
        message.textContent = "Loading report...";
        message.classList.remove("hidden", "error");
    }
}

function showError(text) {
    message.textContent = text;
    message.classList.remove("hidden");
    message.classList.add("error");
}

function setText(id, value) {
    document.querySelector(`#${id}`).textContent = value;
}

function setPnlColor(value) {
    const element = document.querySelector("#total-pnl");
    const number = Number(value);

    element.classList.remove("positive", "negative");

    if (number > 0) {
        element.classList.add("positive");
    } else if (number < 0) {
        element.classList.add("negative");
    }
}

function formatDollars(value) {
    return `$${Number(value).toFixed(2)}`;
}

function formatSignedDollars(value) {
    const number = Number(value);
    const sign = number > 0 ? "+" : "";

    return `${sign}$${number.toFixed(2)}`;
}

function formatOptionalSignedDollars(value) {
    if (value === null) {
        return "N/A";
    }

    return formatSignedDollars(value);
}

function formatPercentage(value) {
    if (value === null) {
        return "N/A";
    }

    return `${(Number(value) * 100).toFixed(1)}%`;
}

function formatMilliseconds(value) {
    if (value === null) {
        return "N/A";
    }

    return `${Number(value).toFixed(1)} ms`;
}

function formatScore(value) {
    return Number(value).toFixed(4);
}