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
