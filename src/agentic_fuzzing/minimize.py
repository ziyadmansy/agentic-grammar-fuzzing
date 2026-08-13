"""Hypothesis shrinking and reproducer verification for campaign failures."""

from hypothesis import find, settings, strategies as st

from .runner import RunResult, run_input


def is_failure(result: RunResult) -> bool:
    return result.status in {"crash", "timeout"} or result.status.startswith("signal:")


def minimize_input(
    command: str | list[str], data: bytes, timeout_seconds: float = 5.0
) -> bytes:
    """Shrink a failing input while preserving its crash or timeout classification."""
    if not is_failure(run_input(command, data, timeout_seconds)):
        raise ValueError("input does not reproduce a crash or timeout")

    candidates = st.binary(min_size=0, max_size=len(data))
    return find(
        candidates,
        lambda candidate: is_failure(run_input(command, candidate, timeout_seconds)),
        settings=settings(max_examples=200, deadline=None, database=None),
    )


def verify_reproducer(
    command: str | list[str], data: bytes, timeout_seconds: float = 5.0
) -> RunResult:
    """Run a minimized input once and return the observed classification."""
    result = run_input(command, data, timeout_seconds)
    if not is_failure(result):
        raise ValueError("reproducer no longer fails")
    return result