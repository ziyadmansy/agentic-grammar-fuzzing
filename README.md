# Agentic Grammar Fuzzing

Black-box grammar-based fuzzing of cJSON with Hypothesis and an LLM refinement loop.

## Target

- Library: [cJSON](https://github.com/DaveGamble/cJSON)
- Version: `v1.7.19`
- Commit: `c859b25da02955fef659d658b8f324b5cde87be`
- Format: JSON
- Grammar source: [ANTLR grammars-v4 JSON.g4](https://github.com/antlr/grammars-v4/blob/master/json/JSON.g4)

The target is exercised as a black box. The harness uses sanitizers only; it does
not use coverage instrumentation or parser internals.

## Quick start

```sh
./scripts/build_target.sh
printf '{}' | ./build/cjson_harness
printf '{]' | ./build/cjson_harness
```

Run the tested baseline campaign with:

```sh
PYTHONPATH=src ./.venv/bin/python scripts/run_baseline.py --examples 500
```

On this Apple Silicon host, the sanitizer runtime currently hangs during
startup even for a clean program. The harness and campaign are therefore
validated locally with `SANITIZERS=none`; sanitizer campaigns should run in a
compatible Xcode/Linux environment:

```sh
SANITIZERS=none ./scripts/build_target.sh
PYTHONPATH=src ./.venv/bin/pytest -q
```

The harness prints a machine-readable result to stdout and reserves stderr for
diagnostics and sanitizer reports.

## Project layout

```text
grammar/       Formal JSON grammar used to design generators
harness/       C stdin adapter for the pinned parser
scripts/       Reproducible build and campaign entry points
src/           Python fuzzing package
tests/         Fast unit and integration tests
vendor/        Pinned target source
```
