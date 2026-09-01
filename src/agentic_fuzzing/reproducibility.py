"""Environment provenance for a completed experiment.

Builds on the run manifests rather than re-deriving what they already record:
seed, timestamp, Python/Hypothesis versions, platform and model all come from
the manifest dict. This module adds only what a manifest cannot know -- which
parser was targeted and at which commit, how the harness was built, and where
the repository stood when the experiment ran.

Nothing here imports the fuzzing engine, and every lookup degrades to
"unknown" rather than raising: a missing compiler string or absent git
metadata must not cost an experiment its results.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shlex
import subprocess
import sys
from typing import Any

UNKNOWN = "unknown"

# Pinned commits for vendored trees that carry no git metadata of their own;
# mirrors the pinned-version table in README.md. vendor/cjson does have a .git,
# so its commit is read from the tree itself and this is only a fallback.
_PINNED_COMMITS = {
    "cjson": "c859b25da02955fef659d658b8f324b5cde87be3",
    "parson": "ba29f4eda9ea7703a9f6a9cf2b0532a2605723c3",
}

_PARSERS = {
    "cjson_harness": ("cJSON", "cjson"),
    "parson_harness": ("parson", "parson"),
}


def _git(repo: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return UNKNOWN
    if completed.returncode != 0:
        return UNKNOWN
    return completed.stdout.decode("utf-8", errors="replace").strip() or UNKNOWN


def _parser_identity(executable: str, repo_root: Path) -> tuple[str, str]:
    name, vendor = _PARSERS.get(Path(executable).name, (UNKNOWN, None))
    if vendor is None:
        return name, UNKNOWN
    vendor_dir = repo_root / "vendor" / vendor
    # git walks up to the enclosing repository, which would silently report this
    # project's commit as the parser's; only trust a tree that is its own root.
    toplevel = _git(vendor_dir, "rev-parse", "--show-toplevel")
    if toplevel != UNKNOWN and Path(toplevel).resolve() == vendor_dir.resolve():
        commit = _git(vendor_dir, "rev-parse", "HEAD")
        if commit != UNKNOWN:
            return name, commit
    return name, _PINNED_COMMITS.get(vendor, UNKNOWN)


def _harness_facts(executable: str) -> dict[str, str]:
    """Read build facts off the binary itself, so they describe what actually ran."""
    path = Path(executable)
    if not path.is_file():
        return {"harness_sha256": UNKNOWN, "compiler": UNKNOWN, "sanitizer_flags": UNKNOWN}
    try:
        data = path.read_bytes()
    except OSError:
        return {"harness_sha256": UNKNOWN, "compiler": UNKNOWN, "sanitizer_flags": UNKNOWN}

    sanitizers = []
    if b"__asan_init" in data:
        sanitizers.append("address")
    if b"__ubsan_handle" in data:
        sanitizers.append("undefined")

    compiler = UNKNOWN
    for marker in (b"Apple clang version ", b"clang version ", b"GCC: ("):
        index = data.find(marker)
        if index != -1:
            raw = data[index : index + 96].split(b"\x00", 1)[0]
            compiler = raw.decode("utf-8", errors="replace").strip()
            break

    return {
        "harness_sha256": hashlib.sha256(data).hexdigest(),
        # release builds on macOS embed no producer string; absence is not a failure
        "compiler": compiler,
        "sanitizer_flags": f"-fsanitize={','.join(sanitizers)}" if sanitizers else "none detected",
    }


def build_report(
    manifest: dict[str, Any],
    *,
    experiment_type: str,
    executable: str,
    runs: int,
    examples_per_run: int,
    max_refinement_iterations: int | None,
    repo_root: Path,
) -> dict[str, Any]:
    """Merge one run manifest with environment facts it cannot record itself."""
    parser, parser_commit = _parser_identity(executable, repo_root)
    seed = manifest.get("seed")
    return {
        "experiment_type": experiment_type,
        "parser": parser,
        "parser_commit": parser_commit,
        "python_version": manifest.get("python_version", UNKNOWN),
        "python_implementation": manifest.get("python_implementation", UNKNOWN),
        "operating_system": f"{platform.system()} {platform.release()}".strip() or UNKNOWN,
        "platform": manifest.get("platform", platform.platform()),
        "hypothesis_version": manifest.get("hypothesis_version", UNKNOWN),
        "model": manifest.get("model") or "not applicable",
        "feedback_mode": manifest.get("feedback_mode") or "not applicable",
        "seed": seed if seed is not None else UNKNOWN,
        "seeds": [seed + index for index in range(runs)] if isinstance(seed, int) else UNKNOWN,
        "runs": runs,
        "examples_per_run": examples_per_run,
        "max_refinement_iterations": max_refinement_iterations
        if max_refinement_iterations is not None
        else "not applicable",
        "timestamp": manifest.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "command_line": shlex.join(sys.argv),
        "git_commit": _git(repo_root, "rev-parse", "HEAD"),
        "git_branch": _git(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
        "harness_executable": executable,
        **_harness_facts(executable),
    }


_LABELS = (
    ("experiment_type", "Experiment type"),
    ("parser", "Parser"),
    ("parser_commit", "Parser commit"),
    ("harness_executable", "Harness executable"),
    ("harness_sha256", "Harness SHA-256"),
    ("compiler", "Compiler"),
    ("sanitizer_flags", "Sanitizer flags"),
    ("python_version", "Python version"),
    ("python_implementation", "Python implementation"),
    ("operating_system", "Operating system"),
    ("platform", "Platform"),
    ("hypothesis_version", "Hypothesis version"),
    ("model", "OpenAI model"),
    ("feedback_mode", "Prompt feedback mode"),
    ("seed", "Base random seed"),
    ("seeds", "Per-run seeds"),
    ("runs", "Number of runs"),
    ("examples_per_run", "Examples per run"),
    ("max_refinement_iterations", "Maximum refinement iterations"),
    ("timestamp", "Execution timestamp (UTC)"),
    ("command_line", "Executed command line"),
    ("git_commit", "Repository commit"),
    ("git_branch", "Repository branch"),
)


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Reproducibility report", "", "| Field | Value |", "|---|---|"]
    for key, label in _LABELS:
        value = report.get(key, UNKNOWN)
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)
        text = str(value).replace("|", "\\|")
        if key in {"harness_sha256", "parser_commit", "git_commit", "command_line", "harness_executable"}:
            text = f"`{text}`"
        lines.append(f"| {label} | {text} |")
    lines += [
        "",
        f'Fields reported as "{UNKNOWN}" were not recoverable in this environment; '
        "they are reported as missing rather than inferred.",
    ]
    return "\n".join(lines) + "\n"


def write_report(directory: Path, report: dict[str, Any], stem: str = "reproducibility") -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{stem}.json"
    markdown_path = directory / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return [json_path, markdown_path]
