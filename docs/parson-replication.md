# parson replication with the real LLM proposer (protocol, fixed before any run)

Written and committed 2026-09-29, before any of the runs below exist.

## Why

The five parson iterations in `artifacts/parson-loop/` (August 2026) did not
call the pipeline's LLM proposer. Each proposal was written outside the loop,
in an interactive session with an AI coding assistant that could read parson's
source, and was then validated and executed through the normal
`load_strategy`/`run_campaign` path. Those iterations are therefore neither
LLM-proposer-driven nor black-box. The paper described them as "a human
standing in for the LLM proposer", which is also inaccurate. This replication
runs parson through the unmodified pipeline exactly as RQ1 ran cJSON.
The August run stays in the repository, relabelled as an exploratory pilot.

## Protocol (identical to the cJSON n=15 comparison except the executable)

- Target: `build/parson_harness`, parson commit `ba29f4e` (v1.5.3), built with
  `scripts/build_parson.sh` (ASan+UBSan). The August binary no longer loads
  because Homebrew LLVM moved from 22 to 23, so the harness was rebuilt with
  Homebrew clang 23.1.0; its SHA-256 is recorded in each reproducibility report.
- Baseline arm: `scripts/run_baseline.py --executable build/parson_harness
  --artifact-dir artifacts/repeated/parson-baseline-n15 --runs 15 --examples 500 --seed 0`
- Refined arm: `scripts/run_refinement.py --executable build/parson_harness
  --artifact-dir artifacts/repeated/parson-refined-n15 --runs 15 --seed 0`
  (defaults: 5 iterations x 500 examples, `gpt-4.1-mini`, temperature 0.2,
  feedback `full`, grammar `grammar/JSON.g4`).
- Seeds 0-14 in both arms.

## Analysis (fixed now)

- Primary outcome: per-run acceptance rate (`accepted / total`, the same
  definition as RQ1). Test: exact two-sided Mann-Whitney U (scipy,
  `method="exact"`), baseline vs refined, n=15 per arm, alpha 0.05. Also
  reported: means, standard deviations, Cliff's delta.
- Descriptive only: crashes/timeouts/signals, structural fingerprints,
  rejection signatures (budgets differ, as in RQ1), and the number of rejected
  proposals.
- Every run is reported. A run is repeated only for an infrastructure failure
  (API error, harness failing to start), and any such repeat is logged here.
- Any sanitizer crash is triaged and minimized before anything is claimed.

## Results (2026-09-29, all 30 pre-registered runs, no protocol changes)

No run was repeated. Commands exactly as above; analysis with
`scripts/parson_stats.py` and `scripts/parson_rejections.py`.

| Arm | Per-run acceptance (%) | Mean (sd) |
|---|---|---|
| Baseline | 95.0, 94.4, 95.8, 96.6, 96.2, 94.6, 96.8, 95.2, 95.6, 97.0, 95.2, 95.6, 95.2, 94.0, 97.0 | 95.61 (0.95) |
| Refined | 96.8, 98.7, 89.05, 93.4, 92.6, 96.5, 88.47, 94.4, 86.67, 89.7, 95.27, 93.1, 96.33, 86.8, 88.4 | 92.41 (3.96) |

- **Primary test.** Refined minus baseline: -3.20 pp; exact two-sided
  Mann-Whitney U = 58.0, p = 0.0235; Cliff's delta = -0.48. Refinement
  *lowered* acceptance. The baseline has tied values, which the exact method
  assumes away; the tie-corrected asymptotic test gives p = 0.025 and a
  permutation test on the difference in means (200,000 resamples, seed 0)
  gives p = 0.0052, so the conclusion does not depend on the ties.
- **Crashes, timeouts, signals:** 0 in 25,500 sanitizer-instrumented
  executions (7,500 baseline, 18,000 refined).
- **Rejected proposals:** 39 of 75 refined iterations (cJSON n=15: 29 of 75).
- **Descriptive:** fingerprints (sum/run) 274.5 baseline vs 513.9 refined;
  rejection signatures (sum/run) 1.0 vs 1.9.

### Mechanism (verified)

- The baseline alternates a grammar-valid document with the same document
  plus one trailing suffix (`,` `]` `}` ` trailing` or NUL). parson accepts
  any bytes after a complete value, so no suffix is ever rejected. All 329
  baseline rejections are objects whose key contains an escaped NUL, which
  parson documents in its source ("We do not support key names with embedded
  \0 chars", parson.c line 973). Acceptance is therefore 1 minus the share of
  documents with such a key.
- Refined arm: 16,545 accepted, 392 encoding errors (counted as
  not accepted, as in RQ1), 1,063 rejected. Every rejection is explained:
  duplicate object key 474, unpaired surrogate escape 427, number overflowing
  a double 138, zero followed by an exponent (`0e5`) 136, NUL in a key 10
  (an input can have several); 6 have no grammar-valid prefix. All but those
  6 are valid under grammar/JSON.g4.
- Each cause confirmed with a minimal document against the harness:
  `{"a":1,"a":2}`, a key containing `\u0000`, `"\udca8"`, `"\ud800"`, `0e5`,
  `-0e5` and `1e400` are rejected; `0.0e5`, `1e-400`, a paired surrogate, a
  NUL in a value and `[1,2] trailing` are accepted. `0e5` is valid under RFC
  8259; support for it was proposed in parson PR #188 (2022, closed
  unmerged). RFC 8259 permits limits on number range.
- Every parson rejection in both arms has the same signature
  (`status=rejected`): parson's parse API returns NULL with no error detail,
  so the rejection-signature proxy carries no information on this target.
