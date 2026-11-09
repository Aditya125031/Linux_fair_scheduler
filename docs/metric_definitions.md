# Scheduler-window Delta metrics

This document defines the offline Delta (Δ) and directional batch-to-interactive (ΔB→I) metrics used by `analyze-run`. They summarize measured scheduler traces. They do not change Linux scheduling and are not simulator output.

## Window inputs

The analyzer forms fixed 50 ms windows in the bpftrace `nsecs` clock domain. It omits one initial warm-up window and any final partial window. For each target TID and window it totals:

- `E_i`: observed CPU service from `sched_switch` intervals.
- `W_i`: observed runnable wait from wakeup-to-switch-in and runnable-preemption-to-switch-in intervals.
- `R_i = E_i + W_i`: observed runnable demand.

Tasks with `R_i < R_min` are omitted. The current default is `R_min = 1 ns`, which excludes only tasks with no observed demand. This explicit initial choice should be revisited with a sensitivity analysis before using the metric for strong conclusions.

The CPU count `M` comes from the run's recorded CPU affinity. The runner also records the current cgroup v2 CPU quota. Delta is available only when that quota is explicitly unlimited; limited or unknown quota status makes the metric unavailable. A task's weight `w_i` comes from its recorded nice value and the standard Linux fair-scheduler nice-to-weight table. The analyzer requires a recorded `SCHED_OTHER` policy for each target task and reports the metric as unavailable if that policy or CPU-affinity metadata is missing.

## Calculations

For each active task in a window of duration `τ`, its fair capacity share and demand-limited entitlement are:

```text
C_i = M × τ × w_i / Σ_j w_j
Ent_i = min(R_i, C_i)
x_i = min(1, E_i / Ent_i)
```

The global deficit and Delta metric are:

```text
d_i = max(x_j) - x_i
Δ = mean(d_i)
```

For the interactive and batch task classes, the analyzer computes mean deficits `m_I` and `m_B` independently, then reports:

```text
ΔB→I = max(0, m_I - m_B)
ΔI→B = max(0, m_B - m_I)
```

Directional values are `null` when a window does not contain active tasks from both classes. The report includes per-window values and summary means, maxima, and nearest-rank p95 values. It does not classify windows using ε or trigger a mitigation decision; the project has not yet selected a measured SLO-derived threshold.

## Limits

- The values are window summaries for the target workload TIDs only; they do not include unrelated system tasks in the weight denominator.
- The nice-to-weight mapping is applicable to the verified `SCHED_OTHER` fair-scheduler tasks required by the analyzer.
- Runnable waits and service are reconstructed from observed trace events. Missing events, trace loss, or trace-boundary effects can bias the totals; the initial and final windows are excluded to reduce boundary effects.
- Workload request timestamps use Python monotonic time and are not joined to the bpftrace clock.
- Per-request CPU service is not measured. The fairness windows use per-TID scheduler intervals.
- A single smoke run is a pipeline check. It is not enough to establish a policy effect or statistical result.
