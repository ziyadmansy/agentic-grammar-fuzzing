import sys

from agentic_fuzzing.minimize import minimize_input, verify_reproducer


def test_minimizes_and_verifies_failure() -> None:
    command = [sys.executable, "-c", "raise SystemExit(1)"]
    minimized = minimize_input(command, b"unnecessary input")

    assert minimized == b""
    assert verify_reproducer(command, minimized).status == "crash"