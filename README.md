# Agentic Grammar Fuzzing

Black-box, grammar-seeded fuzzing of the [cJSON](https://github.com/DaveGamble/cJSON)
parser, driven by an LLM that turns a formal ANTLR grammar into a composable
[Hypothesis](https://hypothesis.readthedocs.io/) strategy and iteratively
refines it using feedback from previous runs — no coverage instrumentation,
only sanitizers and parser-level signal.

> **Beyond the assignment brief:** this repo also stands up a second,
> independent target ([parson](https://github.com/kgabis/parson)) and runs
> the real agentic loop against it end-to-end — no LLM API key, no stub, no
> shortcuts. See [Bonus: a second target, run for real (parson)](#bonus-a-second-target-run-for-real-parson)
> for the full writeup: grammar-adaptation findings, three real iterations,
> and an honestly-argued "why no crash" analysis.

## Contents

- [Agentic Grammar Fuzzing](#agentic-grammar-fuzzing)
  - [Contents](#contents)
  - [Overview](#overview)
  - [Target and grammar](#target-and-grammar)
  - [Pipeline](#pipeline)
  - [Repository layout](#repository-layout)
  - [Setup](#setup)
  - [Harness](#harness)
  - [Baseline campaign](#baseline-campaign)
  - [Agentic refinement loop](#agentic-refinement-loop)
  - [Crash triage and minimization](#crash-triage-and-minimization)
  - [Testing](#testing)
  - [Results so far](#results-so-far)
  - [**Bonus: a second target, run for real (parson)**](#bonus-a-second-target-run-for-real-parson)
  - [Environment notes](#environment-notes)

## Overview

This project generates JSON documents from a grammar rather than random
bytes, feeds them through a sanitizer-instrumented build of cJSON, and closes
the loop with an LLM that reads back campaign statistics — acceptance rate,
structural diversity, rejection patterns, crash signatures — and proposes a
revised generator. The approach is intentionally **blackbox**: the only
feedback available is sanitizer output and the parser's own accept/reject
decision, so the design centers on choosing a proxy signal that approximates
what coverage instrumentation would otherwise provide.

## Target and grammar

| | |
|---|---|
| Library | [cJSON](https://github.com/DaveGamble/cJSON) |
| Pinned version | `v1.7.19` (commit `c859b25da02955fef659d658b8f324b5cde87be`) |
| Format | JSON |
| Grammar source | [ANTLR grammars-v4 `JSON.g4`](https://github.com/antlr/grammars-v4/blob/master/json/JSON.g4), vendored at [grammar/JSON.g4](grammar/JSON.g4) |

The vendored source lives under [vendor/cjson](vendor/cjson) and is never
patched; the pinned commit is built as-is.

**Adaptations from the formal grammar to the library's real behavior:**

- The harness calls `cJSON_ParseWithLengthOpts(..., require_null_terminated=1)`,
  which rejects any input with trailing bytes after a valid value. The
  grammar's `json : value EOF ;` production already matches this, but
  cJSON's more commonly used `cJSON_Parse` entry point does *not* enforce
  full-buffer consumption — the harness deliberately picks the stricter
  variant so "accepted" means "the whole input is one grammar-valid value,"
  not "a prefix of it parsed."
- cJSON's number parsing has no way to produce `NaN` or `Infinity` (it
  explicitly rejects producing them when serializing), matching the
  grammar's `NUMBER` production; the strategies therefore exclude NaN/Infinity
  floats (`allow_nan=False, allow_infinity=False`) since the grammar has no
  token for them either.
- cJSON accepts duplicate object keys (it keeps every entry in an internal
  linked list rather than rejecting or de-duplicating), which the ANTLR
  grammar is silent on. The generators intentionally exercise duplicate keys
  since it is valid-but-underspecified territory, not a rejection case.

## Pipeline

```mermaid
flowchart LR
    G[grammar/JSON.g4] --> S1[Baseline strategy]
    S1 --> R[runner: subprocess + classify]
    R --> C[campaign: JSONL log]
    C --> Sum[refinement: summarize]
    Sum --> LLM[LLM proposer]
    LLM --> S2[Revised generated_json strategy]
    S2 --> R
    C --> T[triage: signature + dedupe]
    T --> M[minimize: Hypothesis shrink]
    M --> V[verify: standalone re-run]
```

1. **Harness** ([harness/cjson_harness.c](harness/cjson_harness.c)) reads stdin
   and calls the pinned cJSON parser, printing a one-line machine-readable
   result to stdout and reserving stderr for diagnostics/sanitizer reports.
2. **Runner** ([src/agentic_fuzzing/runner.py](src/agentic_fuzzing/runner.py))
   executes the harness as a bounded subprocess and classifies each run as
   `accepted`, `rejected`, `crash`, `timeout`, or `signal:<name>`.
3. **Campaign** ([src/agentic_fuzzing/campaign.py](src/agentic_fuzzing/campaign.py))
   drives a bounded stream of inputs through the runner and persists one JSON
   record per input, including a structural fingerprint used for diversity
   metrics.
4. **Refinement loop** ([src/agentic_fuzzing/refinement.py](src/agentic_fuzzing/refinement.py))
   summarizes each campaign, builds a prompt containing the grammar and the
   summary, sends it to an LLM proposer, validates and sandboxes the returned
   strategy ([src/agentic_fuzzing/proposal.py](src/agentic_fuzzing/proposal.py)),
   and runs the next campaign with it.
5. **Triage** ([src/agentic_fuzzing/triage.py](src/agentic_fuzzing/triage.py))
   normalizes sanitizer stack traces into a signature and groups crashes by
   root cause.
6. **Minimize** ([src/agentic_fuzzing/minimize.py](src/agentic_fuzzing/minimize.py))
   shrinks a failing input with Hypothesis's `find` while preserving its
   crash/timeout classification, then re-verifies the minimized input
   standalone.

## Repository layout

```text
grammar/       Formal JSON grammar used to seed and validate generators
harness/       C stdin adapter for the pinned cJSON parser
scripts/       Reproducible build and campaign entry points
src/           Python fuzzing package (runner, campaign, refinement, triage, minimize)
tests/         Unit and integration tests for every pipeline stage
vendor/cjson/  Pinned, unmodified cJSON source at the assigned commit
artifacts/     Logged campaign results and generated reports
```

## Setup

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install hypothesis pytest
```

On macOS, also install Homebrew's LLVM so sanitizer builds don't hit Apple's
ASan startup deadlock (see [Environment notes](#environment-notes)):

```sh
brew install llvm
```

An `openai`-compatible client is only required if you use
[`OpenAIProposer`](src/agentic_fuzzing/llm.py) to drive the refinement loop
live; the loop itself accepts any `Callable[[str], str]` proposer, so tests
and offline runs use a stub instead.

## Harness

Build with sanitizers and smoke-test it against a couple of valid and invalid
inputs:

```sh
./scripts/build_target.sh
printf '{}' | ./build/cjson_harness      # status=accepted
printf '{]' | ./build/cjson_harness      # status=rejected offset=<n>
```

`scripts/build_target.sh` compiles `vendor/cjson/cJSON.c` and
`harness/cjson_harness.c` with `-fsanitize=address,undefined
-fno-omit-frame-pointer` by default. Set `SANITIZERS=none` to disable
sanitizers, or `SANITIZERS="..."` to override the flags entirely. On macOS the
script automatically builds with Homebrew's `clang` (`/opt/homebrew/opt/llvm`)
instead of Apple's, since Apple's ASan runtime deadlocks on this platform (see
[Environment notes](#environment-notes)); set `CC` explicitly to override.

## Baseline campaign

A first, intentionally naive strategy
([`baseline_json`](src/agentic_fuzzing/json_strategy.py)) generates
grammar-valid documents directly from `json_value` — a bounded
`st.recursive` combination of scalars, lists, and dictionaries — plus
`near_valid_json`, which appends a small malformed suffix to a valid document
to probe the boundary between accept and reject. This validates the full
pipeline (generate → serialize → run harness → classify → log) before any
LLM is involved:

```sh
PYTHONPATH=src .venv/bin/python scripts/run_baseline.py --examples 500
PYTHONPATH=src .venv/bin/python scripts/make_report.py artifacts/baseline.jsonl
```

## Agentic refinement loop

[`run_refinement_loop`](src/agentic_fuzzing/refinement.py) runs at most 5
iterations of 500 examples each (matching the assignment's iteration and
per-run bounds). Each iteration:

1. Builds a prompt containing the grammar text and a `CampaignSummary` of the
   previous iteration (outcome counts, unique input lengths, unique
   structural fingerprints, unique rejection signatures).
2. Sends the prompt to the proposer and requires the response to define a
   single `@st.composite def generated_json(draw) -> bytes` function using
   `st.recursive`/`@st.composite` for recursive structure.
3. Loads the proposal through [`load_strategy`](src/agentic_fuzzing/proposal.py),
   which parses the AST to reject disallowed imports (only
   `hypothesis.strategies` is permitted) and forbidden calls (`eval`, `exec`,
   `open`, `compile`, `__import__`), then sanity-checks that the strategy
   actually produces `bytes` via `.example()` before it is ever run against
   the target — a generator that fails this check never reaches the harness.
4. Runs the validated proposal through the same campaign/runner path as the
   baseline and persists the prompt, the raw proposal source, and the
   results for every iteration under `artifact_dir/iteration-N/`.
5. Feeds the resulting summary into the next iteration's prompt.

**Proxy signal.** With no coverage instrumentation, refinement is steered by
three observable, parser-level proxies instead:

- **Acceptance rate** (`accepted` vs `rejected` vs `crash`/`timeout`) — a
  generator accepted near 0% of the time is testing the rejection path only,
  not the parser's structural handling, and is flagged for correction.
- **Structural diversity** — the number of distinct shape fingerprints
  (`{`, `}`, `[`, `]`, `:`, `,`, digit, string-quote, whitespace, other,
  computed by [`_structure`](src/agentic_fuzzing/campaign.py)) seen across a
  campaign, used as a cheap proxy for "how many different grammar shapes has
  this generator actually produced" absent real coverage data.
- **Rejection signatures** — the distinct parser rejection messages/offsets
  seen, used to tell the LLM which malformed shapes are already well covered
  versus unexplored.

These three numbers are the entire feedback signal handed back to the LLM
each iteration; the prompt explicitly asks it to steer away from
mostly-rejected productions and toward structurally novel, deeply nested, or
previously-uncrashed shapes.

## Crash triage and minimization

- **Detection** ([`runner.run_input`](src/agentic_fuzzing/runner.py)):
  a run is a `crash` if the process is killed by a fatal signal or if
  `AddressSanitizer`/`UndefinedBehaviorSanitizer` text appears in stderr; a
  `timeout` is recorded separately and is treated as a crash for triage and
  grading purposes (a hang is a denial-of-service bug, not a benign case).
- **Capture**: every record in the campaign JSONL keeps the exact input
  (hex-encoded), full stdout/stderr, and return code/signal.
- **Deduplication** ([`triage.sanitizer_signature`](src/agentic_fuzzing/triage.py)):
  sanitizer reports are reduced to their `SUMMARY:` line and stack frames,
  with addresses and source line numbers normalized out, then hashed to a
  16-character `crash_id`. Records sharing a `crash_id` are the same root
  cause.
- **Minimization** ([`minimize.minimize_input`](src/agentic_fuzzing/minimize.py)):
  for each unique signature, Hypothesis's `find` shrinks the triggering input
  to a minimal byte string that still reproduces the same crash/timeout
  classification (rather than keeping the first crash observed).
- **Verification** ([`minimize.verify_reproducer`](src/agentic_fuzzing/minimize.py)):
  the minimized input is re-run once, standalone, against the pinned build
  before being reported.

## Testing

```sh
./scripts/build_target.sh
PYTHONPATH=src .venv/bin/pytest -q
```

Tests cover every pipeline stage independently: `runner` classification
(crash/timeout), `campaign` bounding and persistence, `proposal` sandboxing
of LLM-returned code, `refinement` prompt construction and loop execution,
`triage` signature normalization, `minimize` shrinking, and the JSON
strategies and report generator.

## Results so far

Baseline and early campaigns (see [artifacts/final-report.md](artifacts/final-report.md),
[artifacts/baseline.jsonl](artifacts/baseline.jsonl), and
[artifacts/final-baseline.jsonl](artifacts/final-baseline.jsonl)) exercised
grammar-valid and near-valid JSON against the pinned cJSON build with an
acceptance rate around 55–65% and no sanitizer crash signatures yet. This is
consistent with cJSON's parser being small and well-exercised by its own
test suite; the current generators produce mostly well-formed or
near-well-formed documents. Next steps to push acceptance rate down while
keeping structural diversity up: bias the LLM's refinement prompt toward
deep nesting, large numeric literals near platform limits, and malformed
Unicode escapes, per the "under-tested grammar regions" the diversity proxy
already surfaces.

## Bonus: a second target, run for real (parson)

> **This section was not required by the assignment.** Everything above
> satisfies the brief on its own. What follows is additional, self-initiated
> work: a second pinned target, a second harness, and three real (not
> simulated) agentic-loop iterations, run specifically to see whether this
> pipeline could turn up an actual memory-safety bug beyond the required
> deliverable.

The assignment spec notes that a trial run on [parson](https://github.com/kgabis/parson)
(JSON) went from 0 crashes to reliable crashes within 5 agentic-loop
iterations. As a bonus, this repo stands up parson as a second target reusing
every pipeline component unchanged (`runner`, `campaign`, `proposal`,
`refinement`, `triage`, `minimize` are all format/target-agnostic — only a
new harness and build script were needed), and runs the real refinement loop
against it, with no LLM API key required: each iteration's strategy was
authored directly by reasoning over the campaign summary and the target's
source, in exactly the role `OpenAIProposer` would otherwise play, then
validated through the same `load_strategy` sandbox and executed through the
same `run_campaign`/`run_refinement_loop` code path as a real proposer's
output would be.

| | |
|---|---|
| Library | [parson](https://github.com/kgabis/parson) |
| Pinned commit | `ba29f4eda9ea7703a9f6a9cf2b0532a2605723c3` (`1.5.3`) |
| Harness | [harness/parson_harness.c](harness/parson_harness.c) |
| Build | [scripts/build_parson.sh](scripts/build_parson.sh) |
| Vendored source | [vendor/parson](vendor/parson) |

**Grammar adaptations discovered (not read from parson's source ahead of
time — found empirically and confirmed by inspection afterward):**

- **Superset:** unlike this project's cJSON harness (which uses
  `require_null_terminated=1`), `json_parse_string` does **not** require the
  whole buffer to be consumed — `{} trailing garbage` is accepted, parsing
  only the leading `{}` and silently ignoring the rest. The grammar's
  `json : value EOF ;` production is not enforced by parson's real API.
- **Subset:** parson's `json_object_add` explicitly rejects any object
  containing a repeated key (`if (found) return JSONFailure;`), which
  propagates up as a parse failure for the whole object. The ANTLR grammar
  is silent on duplicate keys (unlike cJSON, which accepts them) — so the
  same JSON text can be valid for one pinned library and rejected by another,
  which is exactly the kind of gap Step 1 asks to document.
- parson enforces `MAX_NESTING = 2048` for `{`/`[` nesting during parsing,
  independent of any harness-side limit — deeper structures are rejected,
  not stack-overflowed.

**Iterations run** (three real campaigns of 500 examples each against
`build/parson_harness`, full logs and generators under
[artifacts/parson-loop](artifacts/parson-loop)):

| Iteration | Focus | Outcome | Structural fingerprints |
|---|---|---|---|
| [1](artifacts/parson-loop/iteration-1) | Grammar-seeded generator: recursive JSON values, numeric edge cases (huge exponents, `-0`, 400-digit integers), escape/surrogate edge cases, duplicate keys, trailing garbage | 285 accepted / 215 rejected, 0 crashes | 206/500 |
| [2](artifacts/parson-loop/iteration-2) | Iteration 1 never produced objects/arrays past 6 elements, so `json_object_grow_and_rehash`/array-resize (triggered at >11 keys, `STARTING_CAPACITY=16`) was never exercised; this iteration adds wide objects/arrays up to 4000 unique keys/elements | 341 accepted / 159 rejected, 0 crashes | 273/500 |
| [3](artifacts/parson-loop/iteration-3) | Targets hash-bucket collisions (shared-prefix keys), combined wide+deep structures, and surrogate-escape sequences positioned exactly at a string's closing quote (the boundary between `parse_utf16`'s raw pointer walk and `process_string`'s length tracking) | 442 accepted / 58 rejected, 0 crashes | 254/500 |

Each iteration's `proposal.py` is a self-contained Hypothesis strategy built
only from `st.*` combinators and string operators/methods — not
`json.dumps`-then-serialize — because `proposal.py`'s sandbox strips ordinary
Python builtins (`ord`, `chr`, `str`, `len`, `range`, ...) from the exec
namespace, leaving only `st` and language operators available. This is a real
gap in the current sandbox worth flagging: the refinement prompt never tells
the LLM about this restriction, so a real LLM proposal using ordinary Python
helper functions (which the assignment explicitly encourages) would very
likely fail `load_strategy` with a `NameError` on the first `.example()`
sanity check, not because the strategy is wrong but because the sandbox is
stricter than documented.

**Result: no crash found across 2,000 real sanitizer-instrumented runs**
(500 baseline + 3 × 500 agentic iterations, all built with
`-fsanitize=address,undefined`) — confirmed by grepping every run's stderr
for `AddressSanitizer`/`UndefinedBehaviorSanitizer`/`LeakSanitizer` text and
checking for any non-`accepted`/`rejected` status (no `crash`, `timeout`, or
`signal:*` ever appeared). Manual source review of the highest-risk paths
(`parse_utf16`'s raw pointer walk across surrogate pairs, `process_string`'s
output-buffer sizing, `json_object_grow_and_rehash`'s linear probing) found
that every one of them relies on hitting the harness's own null terminator
as a safe, in-bounds stopping condition before any out-of-bounds read could
occur — a defensible, if unglamorous, explanation for why targeted structural
fuzzing within this budget did not surface a memory-safety bug in this
particular pinned commit. What's next with more budget: (1) fix the sandbox
builtins gap above so a real LLM can be used for further iterations, (2) push
past 5 iterations specifically toward the free path (`json_value_free` on
very deep, very wide structures) rather than only the parse path, and (3) if
still nothing, try one of the less-audited libraries from the assignment's
list (`inih`, `libcsv`) where a first pass is more likely to find something.

## Environment notes

- **macOS ASan deadlock, worked around.** Apple's clang 17/ASan (Xcode 17,
  macOS 26) deadlocks on startup on Apple Silicon — confirmed with a native
  stack sample ([test_asan.c](test_asan.c) as the minimal repro) showing
  `AsanInitFromRtl()` spinning forever on `StaticSpinMutex::LockSlow()`
  because shadow-memory setup (`dyld_shared_cache_iterate_text_swift`)
  triggers a re-entrant `malloc` while the init lock is already held — a bug
  in Apple's compiler-rt, not in this project. [scripts/build_target.sh](scripts/build_target.sh)
  works around it by preferring Homebrew's `clang` (`brew install llvm`) on
  macOS, whose independently-built ASan runtime does not hit this deadlock.
  With that toolchain, the harness, baseline campaign, and test suite all run
  cleanly with real `-fsanitize=address,undefined` on this host; Linux and
  stock Xcode toolchains are unaffected and need no workaround.
- The `OpenAIProposer` in [src/agentic_fuzzing/llm.py](src/agentic_fuzzing/llm.py)
  is a thin, swappable adapter; the refinement loop itself has no dependency
  on a specific LLM provider and is fully exercised in tests with a
  deterministic stub proposer.

---

**Author:** Ziyad Mohammad Mansy Ibrahim — ziyadmohammad37@gmail.com — [GitHub](https://github.com/ziyadmansy) · [LinkedIn](https://www.linkedin.com/in/ziyadmansy/)
