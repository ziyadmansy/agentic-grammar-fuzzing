# Baseline versus refined experiments

| Metric | Baseline (n = 4) | Refined (n = 4) | Absolute difference | Relative difference |
|---|---:|---:|---:|---:|
| Inputs executed (mean per run) | 1125.0 | 1375.0 | +250.0 | +22.2% |
| Accepted (mean per run) | 1076.2 | 1309.2 | +233.0 | +21.6% |
| Rejected (mean per run) | 31.8 | 51.2 | +19.5 | +61.4% |
| Encoding errors (mean per run) | 17.0 | 14.5 | -2.5 | -14.7% |
| Crashes, timeouts and signals (mean per run) | 0.0 | 0.0 | +0.0 | n/a |
| Structural fingerprints (sum over iterations, mean per run) | 457.2 | 503.5 | +46.2 | +10.1% |
| Rejection signatures (sum over iterations, mean per run) | 26.8 | 34.8 | +8.0 | +29.9% |
| Acceptance rate (% of inputs executed) | 96.42 | 95.53 | -0.89 pp | -0.9% |

Values are means over the runs of each arm; differences are refined minus baseline. Relative differences are omitted where the baseline mean is zero. These are descriptive statistics only -- no hypothesis test was performed and no significance is claimed.

Definitions, so the rows are not over-read: the acceptance rate is `accepted / total`, where the denominator includes inputs that failed to encode and so never reached the parser; the crash row counts every outcome that is neither accepted, rejected nor an encoding error, so timeouts and signals are included; and fingerprint and signature counts are summed over each run's iterations, making them upper bounds on a run's distinct shapes rather than de-duplicated totals. All three conventions match `scripts/make_loop_report.py`, so these numbers are comparable with the per-iteration tables in README.md.

**Unequal budgets.** Baseline runs execute 1125 inputs on average and Refined runs 1375. Every count-based row above scales with that budget and is therefore not a like-for-like comparison; only the acceptance rate is scale-free.

- Baseline: `artifacts/repeated/ablation-counts-rejections`
- Refined: `artifacts/repeated/ablation-full`
