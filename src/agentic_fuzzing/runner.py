"""Bounded subprocess execution and result classification for parser inputs."""

from dataclasses import dataclass
import signal
import subprocess
from typing import Optional, Sequence


@dataclass(frozen=True)
class RunResult:
    status: str
    returncode: Optional[int]
    stdout: bytes
    stderr: bytes
    timed_out: bool = False


def run_input(
    command: str | Sequence[str], data: bytes, timeout_seconds: float = 5.0
) -> RunResult:
    """Run one input and classify parser, sanitizer, signal, and timeout outcomes."""
    try:
        completed = subprocess.run(
            command,
            input=data,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        return RunResult(
            status="timeout",
            returncode=None,
            stdout=error.stdout or b"",
            stderr=error.stderr or b"",
            timed_out=True,
        )

    stderr = completed.stderr
    if completed.returncode < 0:
        status = f"signal:{signal.Signals(-completed.returncode).name}"
    elif completed.returncode != 0 or b"AddressSanitizer" in stderr or b"UndefinedBehaviorSanitizer" in stderr:
        status = "crash"
    elif completed.stdout.startswith(b"status=accepted"):
        status = "accepted"
    else:
        status = "rejected"

    return RunResult(status, completed.returncode, completed.stdout, stderr)