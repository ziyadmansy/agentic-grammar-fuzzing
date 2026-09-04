# Baseline versus refined experiments

| Metric | Baseline (n = 15) | Refined (n = 15) | Absolute difference | Relative difference |
|---|---:|---:|---:|---:|
| Inputs executed (mean per run) | 500.0 | 1533.3 | +1033.3 | +206.7% |
| Accepted (mean per run) | 291.1 | 1485.9 | +1194.8 | +410.5% |
| Rejected (mean per run) | 208.9 | 29.9 | -179.0 | -85.7% |
| Encoding errors (mean per run) | 0.0 | 17.5 | +17.5 | n/a |
| Crashes, timeouts and signals (mean per run) | 0.0 | 0.0 | +0.0 | n/a |
| Structural fingerprints (sum over iterations, mean per run) | 274.5 | 598.2 | +323.7 | +117.9% |
| Rejection signatures (sum over iterations, mean per run) | 87.8 | 24.1 | -63.7 | -72.6% |
| Acceptance rate (% of inputs executed) | 58.21 | 97.07 | +38.86 pp | +66.8% |

Values are means over the runs of each arm; differences are refined minus baseline. Relative differences are omitted where the baseline mean is zero. These are descriptive statistics only -- no hypothesis test was performed and no significance is claimed.

Definitions, so the rows are not over-read: the acceptance rate is `accepted / total`, where the denominator includes inputs that failed to encode and so never reached the parser; the crash row counts every outcome that is neither accepted, rejected nor an encoding error, so timeouts and signals are included; and fingerprint and signature counts are summed over each run's iterations, making them upper bounds on a run's distinct shapes rather than de-duplicated totals. All three conventions match `scripts/make_loop_report.py`, so these numbers are comparable with the per-iteration tables in README.md.

**Unequal budgets.** Baseline runs execute 500 inputs on average and Refined runs 1533. Every count-based row above scales with that budget and is therefore not a like-for-like comparison; only the acceptance rate is scale-free.

- Baseline: `artifacts/repeated/cjson-baseline-n15`
- Refined: `artifacts/repeated/cjson-refined-n15`
