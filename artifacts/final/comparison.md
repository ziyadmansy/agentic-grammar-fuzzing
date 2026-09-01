# Baseline versus refined experiments

| Metric | Baseline (n = 5) | Refined (n = 5) | Absolute difference | Relative difference |
|---|---:|---:|---:|---:|
| Inputs executed (mean per run) | 500.0 | 1700.0 | +1200.0 | +240.0% |
| Accepted (mean per run) | 288.2 | 1639.0 | +1350.8 | +468.7% |
| Rejected (mean per run) | 211.8 | 37.6 | -174.2 | -82.2% |
| Encoding errors (mean per run) | 0.0 | 23.4 | +23.4 | n/a |
| Crashes, timeouts and signals (mean per run) | 0.0 | 0.0 | +0.0 | n/a |
| Structural fingerprints (sum over iterations, mean per run) | 276.0 | 616.2 | +340.2 | +123.3% |
| Rejection signatures (sum over iterations, mean per run) | 92.4 | 29.6 | -62.8 | -68.0% |
| Acceptance rate (% of inputs executed) | 57.64 | 96.77 | +39.13 pp | +67.9% |

Values are means over the runs of each arm; differences are refined minus baseline. Relative differences are omitted where the baseline mean is zero. These are descriptive statistics only -- no hypothesis test was performed and no significance is claimed.

Definitions, so the rows are not over-read: the acceptance rate is `accepted / total`, where the denominator includes inputs that failed to encode and so never reached the parser; the crash row counts every outcome that is neither accepted, rejected nor an encoding error, so timeouts and signals are included; and fingerprint and signature counts are summed over each run's iterations, making them upper bounds on a run's distinct shapes rather than de-duplicated totals. All three conventions match `scripts/make_loop_report.py`, so these numbers are comparable with the per-iteration tables in README.md.

**Unequal budgets.** Baseline runs execute 500 inputs on average and Refined runs 1700. Every count-based row above scales with that budget and is therefore not a like-for-like comparison; only the acceptance rate is scale-free.

- Baseline: `artifacts/final/baseline`
- Refined: `artifacts/final/refined`
