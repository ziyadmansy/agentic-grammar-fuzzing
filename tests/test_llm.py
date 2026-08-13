from types import SimpleNamespace

from agentic_fuzzing.llm import OpenAIProposer


class FakeResponses:
    def create(self, **kwargs):
        assert kwargs["max_output_tokens"] == 2500
        return SimpleNamespace(output_text="```python\nreturn 1\n```")


class FakeClient:
    responses = FakeResponses()


def test_openai_proposer_extracts_source() -> None:
    assert OpenAIProposer(FakeClient())("prompt") == "return 1"