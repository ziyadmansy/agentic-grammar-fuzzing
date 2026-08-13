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