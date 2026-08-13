"""Validate and execute the narrow contract returned by a strategy proposer."""

import ast
from collections.abc import Iterable
import builtins

from hypothesis import strategies as st


class ProposalError(ValueError):
    """Raised when generated strategy source does not meet the project contract."""


def load_strategy(source: str):
    """Load a generated ``generated_json`` strategy after lightweight validation."""
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as error:
        raise ProposalError(f"proposal has invalid Python: {error}") from error

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = {alias.name for alias in node.names}
            if isinstance(node, ast.ImportFrom) and node.module == "hypothesis":
                names.discard("strategies")
            if names or (isinstance(node, ast.ImportFrom) and node.module != "hypothesis"):
                raise ProposalError("proposal imports are restricted to hypothesis.strategies")
        if isinstance(node, (ast.Call,)) and isinstance(node.func, ast.Name):
            if node.func.id in {"eval", "exec", "open", "compile", "__import__"}:
                raise ProposalError(f"proposal uses forbidden call: {node.func.id}")

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "hypothesis" and fromlist == ("strategies",):
            return builtins.__import__(name, globals, locals, fromlist, level)
        raise ProposalError("proposal imports are restricted to hypothesis.strategies")

    namespace = {"st": st, "__builtins__": {"__import__": safe_import}}
    exec(compile(tree, "<generated-strategy>", "exec"), namespace, namespace)
    strategy = namespace.get("generated_json")
    if strategy is None or not callable(strategy):
        raise ProposalError("proposal must define callable generated_json")
    try:
        example = strategy().example()
    except Exception as error:
        raise ProposalError(f"generated_json is not a Hypothesis strategy: {error}") from error
    if not isinstance(example, bytes):
        raise ProposalError("generated_json must emit bytes")
    return strategy


def proposal_inputs(source: str, examples: int) -> Iterable[bytes]:
    """Create a bounded stream of examples from validated proposal source."""
    strategy = load_strategy(source)
    for _ in range(examples):
        value = strategy().example()
        if not isinstance(value, bytes):
            raise ProposalError("generated_json emitted a non-bytes value")
        yield value