import sys

from agentic_fuzzing.runner import run_input


def test_runner_classifies_success() -> None:
    result = run_input([sys.executable, "-c", "raise SystemExit(1)"], b"")
    assert result.status == "crash"


def test_runner_classifies_timeout() -> None:
    result = run_input(
        [sys.executable, "-c", "import time; time.sleep(1)"],
        b"",
        timeout_seconds=0.01,
    )
    assert result.status == "timeout"