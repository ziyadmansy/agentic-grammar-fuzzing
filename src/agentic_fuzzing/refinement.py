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


def build_refinement_prompt(grammar: str, summary: CampaignSummary, previous_error: str | None = None) -> str:
    error_section = (
        f"\nThe previous iteration's proposal failed before producing usable data:\n{previous_error}\n"
        if previous_error
        else ""
    )
    return f"""You are refining a Hypothesis strategy for black-box JSON parser fuzzing.

Grammar:
{grammar}

Observed campaign metrics (from the last iteration that produced usable data):
{json.dumps(summary.as_dict(), sort_keys=True)}
{error_section}
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
    # `last_good` is what actually gets shown in the next prompt: it only moves
    # forward on an iteration that produced real campaign data (full or partial),
    # so a total rejection (no data at all) falls back to whatever the last real
    # campaign was -- possibly several iterations back -- instead of resetting
    # the refinement chain. `last_error` carries the previous failure's exact
    # exception text into the next prompt so the proposer knows what broke.
    last_good = CampaignSummary(Counter(), 0, 0, 0, 0)
    last_error: str | None = None
    for iteration in range(min(iterations, 5)):
        prompt = build_refinement_prompt(grammar, last_good, last_error)
        proposal = proposer(prompt)
        iteration_dir = artifact_dir / f"iteration-{iteration + 1}"
        iteration_dir.mkdir(parents=True, exist_ok=True)
        (iteration_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
        (iteration_dir / "proposal.py").write_text(proposal, encoding="utf-8")
        result_path = iteration_dir / "results.jsonl"
        try:
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
        except Exception as error:
            # bad LLM-generated code can raise anything (NameError mid-generation,
            # UnicodeEncodeError on a stray surrogate, etc.), not just ProposalError,
            # and can fail partway through the 500 examples -- a single bad proposal
            # must not abort the remaining iterations. Keep whatever examples the
            # campaign did manage to log before the crash, rather than discarding
            # real (if incomplete) data.
            error_text = f"{type(error).__name__}: {error}"
            (iteration_dir / "proposal_error.txt").write_text(error_text, encoding="utf-8")
            last_error = error_text
            if result_path.exists() and result_path.stat().st_size > 0:
                with result_path.open(encoding="utf-8") as result_file:
                    partial = summarize_records(json.loads(line) for line in result_file)
                last_good = partial
                summaries.append(partial)
            else:
                # total rejection, zero data -- leave last_good pointing at the
                # last iteration that actually produced data, don't overwrite it.
                summaries.append(CampaignSummary(Counter({"proposal_rejected": 1}), 0, 0, 0, 1))
            continue
        with result_path.open(encoding="utf-8") as result_file:
            summary = summarize_records(json.loads(line) for line in result_file)
        last_good = summary
        last_error = None
        summaries.append(summary)
    return summaries