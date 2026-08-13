"""LLM refinement orchestration with bounded iterations and persisted proposals."""

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Iterable

from .campaign import run_campaign
from .proposal import proposal_inputs


@dataclass(frozen=True)
class CampaignSummary:
    counts: Counter[str]
    unique_lengths: int
    unique_structures: int
    unique_rejections: int
    total: int

    def as_dict(self) -> dict[str, object]:
        return {
            "counts": dict(self.counts),
            "unique_lengths": self.unique_lengths,
            "unique_structures": self.unique_structures,
            "unique_rejections": self.unique_rejections,
            "total": self.total,
        }


def summarize_records(records: Iterable[dict[str, object]]) -> CampaignSummary:
    counts: Counter[str] = Counter()
    lengths: set[int] = set()
    structures: set[str] = set()
    rejections: set[str] = set()
    total = 0
    for record in records:
        total += 1
        counts[str(record["status"])] += 1
        lengths.add(int(record["input_length"]))
        structures.add(str(record.get("structure", "")))
        if record["status"] == "rejected":
            rejections.add(str(record.get("rejection_signature", "")))
    return CampaignSummary(counts, len(lengths), len(structures), len(rejections), total)


def build_refinement_prompt(grammar: str, summary: CampaignSummary) -> str:
    return f"""You are refining a Hypothesis strategy for black-box JSON parser fuzzing.

Grammar:
{grammar}

Observed campaign metrics:
{json.dumps(summary.as_dict(), sort_keys=True)}

Return only Python source defining `@st.composite def generated_json(draw) -> bytes`.
Use bounded `st.recursive` or `@st.composite`, preserve valid and near-valid cases,
and keep recursion and output sizes bounded. The campaign runs at most 500 examples
per iteration. Do not use subprocesses, filesystem,
network access, eval, exec, or coverage instrumentation.
"""


def run_refinement_loop(
    executable: str,
    grammar_path: Path,
    proposer: Callable[[str], str],
    artifact_dir: Path,
    iterations: int = 5,
    examples_per_iteration: int = 500,
    timeout_seconds: float = 5.0,
    input_factory: Callable[[str, int], Iterable[bytes]] | None = None,
) -> list[CampaignSummary]:
    """Run bounded campaigns and persist each LLM proposal for review."""
    summaries: list[CampaignSummary] = []
    grammar = grammar_path.read_text(encoding="utf-8")
    previous = CampaignSummary(Counter(), 0, 0, 0, 0)
    for iteration in range(min(iterations, 5)):
        prompt = build_refinement_prompt(grammar, previous)
        proposal = proposer(prompt)
        iteration_dir = artifact_dir / f"iteration-{iteration + 1}"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        (iteration_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        (iteration_dir / "proposal.py").write_text(proposal, encoding="utf-8")
        result_path = iteration_dir / "results.jsonl"
        inputs = (
            input_factory(proposal, min(examples_per_iteration, 500))
            if input_factory is not None
            else proposal_inputs(proposal, min(examples_per_iteration, 500))
        )
        run_campaign(
            executable,
            inputs,
            result_path,
            max_examples=min(examples_per_iteration, 500),
            timeout_seconds=timeout_seconds,
        )
        with result_path.open(encoding="utf-8") as result_file:
            previous = summarize_records(json.loads(line) for line in result_file)
        summaries.append(previous)
    return summaries