# Reproducibility report

| Field | Value |
|---|---|
| Experiment type | baseline |
| Parser | cJSON |
| Parser commit | `c859b25da02955fef659d658b8f324b5cde87be3` |
| Harness executable | `build/cjson_harness` |
| Harness SHA-256 | `702d52001164c50f1d9cf58562d8d47c85c8f1b2907e09d82fc77148716a5235` |
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
| Execution timestamp (UTC) | 2026-10-18T22:42:28.039524+00:00 |
| Executed command line | `scripts/run_baseline.py --executable build/cjson_harness --artifact-dir artifacts/repeated/cjson-baseline-validonly-n15 --runs 15 --examples 500 --seed 0 --valid-only` |
| Repository commit | `100511e13df16b26076e4d98da817d3c8073c171` |
| Repository branch | main |

Fields reported as "unknown" were not recoverable in this environment; they are reported as missing rather than inferred.
