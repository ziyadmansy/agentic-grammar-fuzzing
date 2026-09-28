# Reproducibility report

| Field | Value |
|---|---|
| Experiment type | baseline |
| Parser | parson |
| Parser commit | `ba29f4eda9ea7703a9f6a9cf2b0532a2605723c3 (documented, not verified)` |
| Harness executable | `build/parson_harness` |
| Harness SHA-256 | `cd0dd420ba72bfedb4a4bc10b5101d38eaa0c8c43db1ddd706daefe439f27da4` |
| Compiler | unknown |
| Sanitizer flags | -fsanitize=address,undefined |
| Python version | 3.14.7 (main, Aug  5 2026, 10:29:49) [Clang 21.0.0 (clang-2100.1.1.101)] |
| Python implementation | CPython |
| Operating system | Darwin 25.5.0 |
| Platform | macOS-26.5.2-arm64-arm-64bit-Mach-O |
| Hypothesis version | 6.165.5 |
| OpenAI model | not applicable |
| Prompt feedback mode | not applicable |
| Base random seed | 0 |
| Per-run seeds | 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 |
| Number of runs | 15 |
| Examples per run | 500 |
| Maximum refinement iterations | not applicable |
| Execution timestamp (UTC) | 2026-09-28T22:50:46.934546+00:00 |
| Executed command line | `scripts/run_baseline.py --executable build/parson_harness --artifact-dir artifacts/repeated/parson-baseline-n15 --runs 15 --examples 500 --seed 0` |
| Repository commit | `830ae29b18be56fe1f5f159c49cb765072900959` |
| Repository branch | main |

Fields reported as "unknown" were not recoverable in this environment; they are reported as missing rather than inferred.
