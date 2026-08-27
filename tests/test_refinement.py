from collections import Counter
import sys

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