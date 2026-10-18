# No-feedback control arm (protocol, fixed before any run)

Written and committed 2026-10-19, before any of the runs below exist.

## Why

In the cJSON n=15 refined arm (`artifacts/repeated/cjson-refined-n15`), the first
iteration's prompt carries an all-zero metrics object, because no campaign has run
yet, and no prompt ever shows the previous generator's source. Pooled over the
committed data, the 15 iterations written before any campaign result reached the
proposer have 98.1% acceptance, and the 31 written after one have 96.3%. That is
an observation, not a test: iterations after a failed proposal also differ in
that they carry the error text. This arm tests directly whether the campaign
feedback changes acceptance, by removing it and changing nothing else.

A second, LLM-free check measures what the static baseline's grammar-valid half
alone reaches. The baseline alternates `baseline_json` with `near_valid_json`
(the same document plus a trailing suffix), so its acceptance is bounded by
construction.

## Protocol

- **Target:** `build/cjson_harness`, cJSON v1.7.19 (commit `c859b25`), built with
  `scripts/build_target.sh` (ASan+UBSan). The August binary no longer loads,
  because Homebrew LLVM moved from 22 to 23 (as for the parson replication). It
  was rebuilt with Homebrew clang 23.1.0, and its SHA-256 is recorded in each
  reproducibility report. Equivalence check, run before this arm: the seeded
  n=15 baseline (`scripts/run_baseline.py --runs 15 --examples 500 --seed 0`) is
  replayed on the rebuilt binary and must give the committed per-input outcomes
  of `artifacts/repeated/cjson-baseline-n15` exactly. The result is appended below.
- **No-feedback arm (Group B):** `scripts/run_refinement.py --executable
  build/cjson_harness --artifact-dir artifacts/repeated/cjson-nofeedback-n15
  --runs 15 --seed 0 --feedback no-feedback`. Defaults otherwise: 5 iterations ×
  500 examples, `gpt-4.1-mini`, temperature 0.2, grammar `grammar/JSON.g4`,
  2,500 output tokens. Every iteration's prompt is byte-identical to the first
  prompt of the refined arm (`tests/test_refinement.py`; all 15 committed
  iteration-1 prompts of `cjson-refined-n15` match it). No campaign metric and no
  previous error ever reaches the proposer. Failed proposals are handled exactly
  as in the refined arm: the iteration executes no inputs.
- **Comparison arm (Group A):** the committed `artifacts/repeated/cjson-refined-n15`
  (feedback `full`), not re-run.
- **Valid-half baseline:** `scripts/run_baseline.py --executable build/cjson_harness
  --artifact-dir artifacts/repeated/cjson-baseline-validonly-n15 --runs 15
  --examples 500 --seed 0 --valid-only`. No LLM.
- **Seeds:** 0–14 in every arm, as in RQ1.

## Analysis (fixed now)

- **Primary outcome:** per-run acceptance rate (`accepted / total`, encoding
  errors in the denominator, the RQ1 definition), Group A against Group B. Exact
  two-sided Mann–Whitney U (scipy, `method="exact"`), n=15 per arm, alpha 0.05,
  with means, standard deviations and Cliff's delta.
- **Decision rules:**
  - A > B at p < 0.05: campaign feedback raises acceptance.
  - B > A at p < 0.05: feedback lowers acceptance.
  - p ≥ 0.05 with |δ| < 0.33: no detectable effect of feedback on acceptance at
    n=15. The acceptance gain over the static baseline is then attributed to the
    proposer's feedback-free generators.
  - p ≥ 0.05 with |δ| ≥ 0.33: not detected, effect size reported, no claim either way.
- **Secondary, descriptive only:** Group B against the static baseline
  (acceptance, exact Mann–Whitney U); the valid-half baseline's acceptance; per
  arm, the share of executed inputs rejected, distinct structural fingerprints
  per 500-input iteration (sum over iterations divided by iterations with data),
  rejected proposals, and crashes, timeouts and signals.
- Every run is reported. A run is repeated only for an infrastructure failure
  (API error, harness failing to start), and any such repeat is logged here.
- Any sanitizer crash is triaged and minimized before anything is claimed.
- Analysis script: `scripts/nofeedback_stats.py`, committed with the results.

## Results

**Binary equivalence (2026-10-19, before any LLM call).** The rebuilt harness
(Homebrew clang 23.1.0, SHA-256 `702d5200…a5235`) replayed the seeded n=15
baseline. All 7,500 records match `artifacts/repeated/cjson-baseline-n15` in
input bytes and outcome (0 differ).

**Arm results (2026-10-19, all 15 pre-registered runs, no protocol changes).**
No run was repeated: every failed proposal is an ordinary code error (mostly
Hypothesis API misuse, as in the refined arm), and no API or harness failure
occurred. Analysis: `scripts/nofeedback_stats.py` with the four arm directories.

| Arm | Runs with data | Mean acceptance (sd) | Rejected inputs | Shapes per 500-input iteration | Failed proposals |
|---|---|---|---|---|---|
| Static baseline | 15/15 | 58.21% (1.30) | 41.79% | 274.5 | – |
| Valid-half baseline | 15/15 | 100.00% (0.00) | 0.00% | 251.0 | – |
| Refined, feedback `full` (A) | 15/15 | 97.07% (2.93) | 1.95% | 195.1 | 29 of 75 |
| No feedback (B) | 14/15 | 92.95% (15.53) | 3.23% | 174.0 | 52 of 75 |

Per-run acceptance, no feedback: 40.0, 95.1, 96.6, 91.6, 96.2, 94.33, (no
data: all 5 proposals failed), 100.0, 99.8, 91.4, 100.0, 100.0, 99.0, 97.8, 99.4.
The 40.0% run's only working generator emitted 193 unencodable strings (lone
surrogates), which count as not accepted.

- **Primary (A vs B):** +4.13 pp, exact two-sided Mann–Whitney U = 103.0,
  p = 0.949, Cliff's δ = −0.02. By the rule above (p ≥ 0.05, |δ| < 0.33): no
  detectable effect of feedback on acceptance at n=15. The acceptance gain over
  the static baseline is attributed to the proposer's feedback-free generators.
- **Secondary (B vs static baseline):** +34.73 pp, U = 195.0, p = 1.76e-05, δ = +0.86.
- **Exploratory (not pre-registered):** failed proposals per run, A vs B (1–3 vs
  1–5 of 5), exact two-sided Mann–Whitney p = 0.0005. The refined arm's prompt
  carries both the campaign metrics and the previous error text, so this arm
  cannot separate the two; since the failures are code errors, the error text is
  the plausible cause.
