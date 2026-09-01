from collections import Counter
import sys

import pytest

from agentic_fuzzing.refinement import (
    CampaignSummary,
    build_refinement_prompt,
    run_refinement_loop,
)


def test_refinement_prompt_contains_constraints() -> None:
    prompt = build_refinement_prompt("json : value EOF;", CampaignSummary(Counter(), 0, 0, 0, 0))

    assert "st.recursive" in prompt
    assert "500" in prompt
    assert "coverage instrumentation" in prompt


def test_refinement_prompt_includes_previous_error_when_given() -> None:
    prompt = build_refinement_prompt(
        "json : value EOF;", CampaignSummary(Counter(), 0, 0, 0, 0), previous_error="TypeError: boom"
    )

    assert "TypeError: boom" in prompt


def test_refinement_prompt_omits_error_section_by_default() -> None:
    prompt = build_refinement_prompt("json : value EOF;", CampaignSummary(Counter(), 0, 0, 0, 0))

    assert "previous iteration's proposal failed" not in prompt


def test_refinement_prompt_feedback_modes_restrict_visible_metrics() -> None:
    summary = CampaignSummary(Counter({"accepted": 3}), 1, 2, 4, 5)
    grammar = "json : value EOF;"

    counts_only = build_refinement_prompt(grammar, summary, feedback_mode="counts")
    with_rejections = build_refinement_prompt(grammar, summary, feedback_mode="counts+rejections")
    full = build_refinement_prompt(grammar, summary, feedback_mode="full")

    for prompt in (counts_only, with_rejections, full):
        assert '"accepted": 3' in prompt and '"total": 5' in prompt
    assert "unique_rejections" not in counts_only
    assert "unique_structures" not in counts_only
    assert '"unique_rejections": 4' in with_rejections
    assert "unique_structures" not in with_rejections
    assert '"unique_structures": 2' in full and '"unique_lengths": 1' in full
    # the default must stay the current, unrestricted behaviour
    assert build_refinement_prompt(grammar, summary) == full


def test_refinement_prompt_rejects_unknown_feedback_mode() -> None:
    with pytest.raises(ValueError):
        build_refinement_prompt("json : value EOF;", CampaignSummary(Counter(), 0, 0, 0, 0), feedback_mode="none")


def test_refinement_loop_executes_generated_proposal(tmp_path) -> None:
    grammar_path = tmp_path / "JSON.g4"
    grammar_path.write_text("json : value EOF ;", encoding="utf-8")
    source = (
        "from hypothesis import strategies as st\n"
        "@st.composite\n"
        "def generated_json(draw):\n"
        "    return draw(st.just(b'{}'))\n"
    )
    summaries = run_refinement_loop(
        sys.executable,
        grammar_path,
        lambda prompt: source,
        tmp_path / "iterations",
        iterations=1,
        examples_per_iteration=2,
        timeout_seconds=1,
    )

    assert summaries[0].counts["rejected"] == 2
    assert (tmp_path / "iterations/iteration-1/proposal.py").exists()


def test_refinement_loop_carries_forward_last_good_summary_across_rejection(tmp_path) -> None:
    grammar_path = tmp_path / "JSON.g4"
    grammar_path.write_text("json : value EOF ;", encoding="utf-8")
    good_source = (
        "from hypothesis import strategies as st\n"
        "@st.composite\n"
        "def generated_json(draw):\n"
        "    return draw(st.just(b'{}'))\n"
    )
    # missing draw parameter -> strategy() raises TypeError with zero campaign data
    broken_source = "def generated_json():\n    return b'{}'\n"
    proposals = [good_source, broken_source, good_source]
    calls = iter(proposals)

    run_refinement_loop(
        sys.executable,
        grammar_path,
        lambda prompt: next(calls),
        tmp_path / "iterations",
        iterations=3,
        examples_per_iteration=2,
        timeout_seconds=1,
    )

    assert (tmp_path / "iterations/iteration-2/proposal_error.txt").exists()
    error_text = (tmp_path / "iterations/iteration-2/proposal_error.txt").read_text(encoding="utf-8")

    iteration_3_prompt = (tmp_path / "iterations/iteration-3/prompt.txt").read_text(encoding="utf-8")
    # iteration 3 must see iteration 1's real data (total=2), not the rejection marker
    assert '"total": 2' in iteration_3_prompt
    assert "proposal_rejected" not in iteration_3_prompt
    # and it must see iteration 2's exact failure text
    assert error_text in iteration_3_prompt