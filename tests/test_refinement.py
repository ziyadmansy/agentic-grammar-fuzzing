from collections import Counter

from agentic_fuzzing.refinement import CampaignSummary, build_refinement_prompt


def test_refinement_prompt_contains_constraints() -> None:
    prompt = build_refinement_prompt("json : value EOF;", CampaignSummary(Counter(), 0, 0))

    assert "st.recursive" in prompt
    assert "500" in prompt
    assert "coverage instrumentation" in prompt