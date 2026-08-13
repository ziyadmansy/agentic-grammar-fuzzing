"""Optional OpenAI proposer used by the bounded refinement loop."""

from typing import Any


class OpenAIProposer:
    """Turn refinement prompts into strategy source without hiding API failures."""

    def __init__(self, client: Any, model: str = "gpt-4.1-mini") -> None:
        self.client = client
        self.model = model

    def __call__(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0.2,
            max_output_tokens=2500,
        )
        text = getattr(response, "output_text", None)
        if not text:
            raise RuntimeError("LLM response did not contain output_text")
        return _strip_code_fence(text)


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return cleaned