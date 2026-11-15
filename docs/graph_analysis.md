# Graphs and interpreting the pilot

## What the comparison chart shows

Run `plot-runs` on completed matching run directories. It creates one SVG with seven panels: approximate interactive response p95 and p99, interactive turnaround p95, batch throughput, global Delta, directional Delta B→I, and directional Delta I→B. Every measured policy group is shown separately, including each fixed batch nice value. Bars are means of run-level metrics; whiskers are descriptive bootstrap intervals when at least two runs contribute. The SVG also includes a `Wait-aware (simulator only)` category marked **not measured** for all performance outcomes.

For the other views supported by existing run files, `plot-diagnostics` writes five SVGs: an interactive response CDF, a runnable-wait CDF split by workload class, per-target-TID CPU-service CDF, eligible scheduler-window Delta CDFs, and a per-run response/throughput scatter plot. These show samples across runs, not independent workers. The current smoke workload has only one batch worker. Therefore it cannot produce the spec's graph of p95/p99 latency under increasing batch-worker contention, and the per-task service chart is not a multi-worker distribution. Fixed nice levels change scheduling weights; they are not batch-worker-count contention levels.

The baseline label says `EEVDF baseline (kernel default)`. This identifies the default `SCHED_OTHER` workload configuration used in the reported Ubuntu guest. The analyzer verifies Linux scheduling class metadata, but it does not independently identify the kernel's internal fair-scheduler implementation; check the actual guest kernel/build before making a precise EEVDF claim.

## Workload and observation sequence

The quick configuration uses one interactive process and one CPU-bound batch process for five seconds. The interactive process intends a request release every 100 ms and performs a deterministic 10,000-iteration CPU burst per request, so about 50 requests are expected per run; use the recorded request count, not the expectation, in analysis. The batch process continuously performs 100,000-iteration work units and records its completed-unit count at the end. Under fixed nice, only this batch worker receives the configured nice value (for example, +5); the interactive process remains at the runner's normal nice value.

For each run, the collector starts first, then the interactive and batch processes run concurrently while scheduler wakeup and context-switch events are recorded. The trace is system-wide during the short collection window; analysis selects the verified numeric TIDs of the two project workloads. The pilot runs policies sequentially, one run at a time.

The source records are:

- `results/raw/<run-id>/interactive.jsonl`: one row per interactive request, with release, first user-space execution-start, and completion timestamps. These three timestamps yield approximate response time and turnaround.
- `results/raw/<run-id>/batch.json`: one final row with the batch TID, nice value, elapsed time, completed units, and exit status. There is no per-unit timestamp sequence in this workload log.
- `results/raw/<run-id>/scheduler.tsv`: the chronological scheduler-event stream, including unrelated system tasks. The TIDs in the manifest identify which events belong to the interactive and batch processes.
- `results/processed/<run-id>/analysis.json`: request percentiles, batch throughput, reconstructed runnable waits, scheduler-observed service, Delta window summaries, and warnings.

Delta uses active verified target-task records in scheduler-clock windows. Directional class values are available only for windows containing both workload classes. It is a separate scheduler trace metric, not derived from Python request timestamps.

## How to read each panel

- **Approximate response p95:** within each run, the 95th percentile of execution-start minus intended-release across recorded requests. The chart then averages those per-run p95 values; it does not pool all requests from all runs.
- **Turnaround p95:** within each run, the 95th percentile of completion minus intended-release; summarized across runs the same way.
- **Batch throughput:** completed fixed work units divided by that run's measured elapsed seconds.
- **Global and directional Delta:** per-run means across eligible scheduler windows, then summarized across runs. Lower values indicate smaller normalized deficits under the project's metric definition.
- **Wait-aware:** the project implementation is an offline decision simulator. It does not run as a scheduler policy and produces no measured response, throughput, or Delta outcome. The chart leaves those values blank instead of inventing a result.

## Example using the six-run output shared by the user

The following is a small sample transcribed from the user's `aggregate-runs` output on 2026-11-09. Each policy has three runs, so the policy-level chart value is an average of three per-run summaries:

| Policy group | Batch throughput mean | Interactive response p95 mean | Response p95 median across runs | Global Delta mean |
|---|---:|---:|---:|---:|
| Kernel-default baseline | 103.86 units/s | 49.11 ms | 3.48 ms | 0.0253 |
| Fixed batch nice +5 | 55.78 units/s | 1.64 ms | 1.58 ms | 0.0408 |
| Wait-aware simulator | Not measured | Not measured | Not measured | Not measured |

The baseline response p95 mean is much higher than its across-run median, so at least one run may be an outlier; inspect all three `analysis.json` files and manifests before interpreting the mean. The observed numbers describe this small pilot only. They do not establish statistical significance or prove that changing nice caused the differences. The directional Delta means in the same output were ΔB→I 0.104 baseline versus 0.149 at nice +5, and ΔI→B 0.044 versus 0.016. These are descriptive trace-window summaries.

## Commands in the Ubuntu KVM

After the code update is in the guest, from the repository root:

```bash
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
sudo -v
python3 -m cpu_fairness.cli run-nice-sweep \
  --nice-values 3 10 \
  --repeats 3 \
  --output-root results
```

This makes nine sequential five-second runs: three baselines, three nice +3 runs, and three nice +10 runs. It preserves each run separately and stops at the first failure. The sweep is optional if only baseline versus the already measured nice +5 is needed.

For the existing six run IDs from the user's pilot, make the SVG chart without installing Matplotlib:

```bash
python3 -m cpu_fairness.cli plot-runs \
  results/raw/quick-smoke-20261109T165112Z-0c17b9c7 \
  results/raw/quick-fixed-nice-20261109T165122Z-a8282eca \
  results/raw/quick-smoke-20261109T165135Z-7b1d34ca \
  results/raw/quick-fixed-nice-20261109T165146Z-db84089e \
  results/raw/quick-smoke-20261109T165202Z-d627a5dd \
  results/raw/quick-fixed-nice-20261109T165227Z-ea1ddb0d \
  --output results/figures/pilot-comparison.svg
```

To generate the additional distributions and trade-off graphs from these same runs:

```bash
python3 -m cpu_fairness.cli plot-diagnostics \
  results/raw/quick-smoke-20261109T165112Z-0c17b9c7 \
  results/raw/quick-fixed-nice-20261109T165122Z-a8282eca \
  results/raw/quick-smoke-20261109T165135Z-7b1d34ca \
  results/raw/quick-fixed-nice-20261109T165146Z-db84089e \
  results/raw/quick-smoke-20261109T165202Z-d627a5dd \
  results/raw/quick-fixed-nice-20261109T165227Z-ea1ddb0d \
  --output-prefix results/figures/pilot
```

It writes `pilot.response-cdf.svg`, `pilot.runnable-wait-cdf.svg`, `pilot.cpu-service.svg`, `pilot.delta-windows-cdf.svg`, and `pilot.latency-throughput.svg`. If Delta or wait samples are unavailable, the corresponding CDF is marked empty rather than fabricated. Choose a fresh output prefix for each generation.

The command reprocesses each run's large raw trace once and prints `Analyzing trace i/N` progress on stderr. It reads run directories but writes plots only after it has collected all run data. You may interrupt during trace processing without changing the raw run data; use a new output prefix if all five graphs had already been written.

If you also ran a nice sweep, add each emitted `results/raw/<run-id>` path to the same `plot-runs` command. The combined run list must use matching workload settings, and each policy group needs at least two runs for an interval. The aggregate JSON printed by `aggregate-runs` includes individual run-level values; save it with shell redirection if a file is desired. Never overwrite prior plots or run outputs; choose a fresh filename.

To inspect the request sequence and the batch summary for one run without dumping the full scheduler trace:

```bash
RUN_ID='paste-run-id-here'
cat "results/raw/$RUN_ID/interactive.jsonl"
cat "results/raw/$RUN_ID/batch.json"
```

The scheduler trace itself is the combined chronological task-switch/wakeup sequence; `analysis.json` and `wait_episodes.jsonl` contain its selected, reconstructed target-task analysis. Keep the original raw TSV unchanged.
