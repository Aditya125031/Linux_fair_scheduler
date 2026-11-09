# First smoke experiment: Ubuntu guest checklist

This guide runs one short baseline mixed-workload experiment. It does not run the full matrix. Do not run it on a production host. The Python runner and workloads stay unprivileged; the collector subprocess alone invokes bpftrace through `sudo -n`.

## Bring the updated checkout into the guest

Use the Ubuntu guest's existing project checkout after the Windows changes have been transferred or committed and pulled. From that checkout's root:

```bash
cd ~/Linux_fair_scheduler
git status --short
```

Confirm that `src/cpu_fairness/`, `scripts/preflight.sh`, `scripts/smoke_test.sh`, and this guide are present. If the repository is not shared with the guest, copy/sync the updated working tree before continuing. Do not copy the existing root CSV files over any guest files.

## Check Python and authorize the collector

```bash
python3 --version
python3 -m pip --version
sudo -v
```

The report says the guest has Python 3.14.4. This project foundation has no runtime third-party dependencies, so a virtual environment is optional for this smoke. Do not run the CLI with `sudo`.

If `python3` is not the reported Python 3.14 interpreter, stop and report its actual version before proceeding. The `sudo -v` command prompts once; the runner later uses `sudo -n` and fails clearly if that authorization has expired.

## Run preflight

From the repository root:

```bash
set -o pipefail
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m cpu_fairness.cli preflight --json | tee /tmp/cpu-fairness-preflight.json
```

Expected: JSON reports `"ready": true`; both `sched_wakeup` and `sched_switch` are present, each required field is found in that event's tracefs `format` file, and BTF, tracefs, cgroup v2, bpftrace, and `sudo -n bpftrace --version` checks pass. A failed check returns exit code 2. Do not continue to the smoke if preflight fails; send the JSON and error output for review.

The sudo check confirms that cached noninteractive sudo can execute bpftrace; it does not claim a tracepoint attach has succeeded. The collector's READY marker is emitted from a 10 ms interval probe after bpftrace has attached its probes. The prior manual `sched_wakeup` smoke is supporting environment evidence, not a pass for this collector.

## Run one smoke experiment

The checked-in `configs/quick.json` runs one interactive process and one batch process for five seconds. The collector starts first and records only `sched_wakeup` and `sched_switch` system-wide during that short window. Analysis then filters records by verified workload TIDs. Raw events for unrelated tasks may also appear in the trace and are retained.

```bash
python3 -m cpu_fairness.cli smoke --config configs/quick.json --output-root results | tee /tmp/cpu-fairness-smoke.json
```

Expected: command returns a JSON manifest with `"status": "completed"`, distinct process records for interactive and batch, `single_threaded_verified: true`, a collector exit status, event counts, and output paths. A successful smoke also requires at least one complete target-task wait episode. Failures are saved in that run's manifest and are not represented as success.

Each run uses a unique ID. Results are separated as:

- `results/raw/<run-id>/scheduler.tsv`: original machine-readable trace events with a schema header.
- `results/raw/<run-id>/bpftrace.stderr.log`: collector diagnostics and potential loss warnings.
- `results/raw/<run-id>/interactive.jsonl` and `batch.json`: workload records.
- `results/raw/<run-id>/manifest.json`: actual system facts, process identities, statuses, and paths.
- `results/processed/<run-id>/wait_episodes.jsonl`, `task_accounting.json`, and `analysis.json`: trace-derived output.

The raw TSV columns are `timestamp_ns`, `event`, `tid`, `prev_tid`, `next_tid`, `prev_state`, `prio`, `prev_prio`, `next_prio`, `cpu`, and `target_cpu`. A `WAKEUP` record uses `tid`; a `SWITCH` record uses `prev_tid`, `next_tid`, and `prev_state`. A value of `-1` means that field does not apply to that event. `END` carries the latest trace-clock heartbeat. No process names or aggregate counts are used as the raw event dataset.

Never edit the raw trace when reviewing or processing it. The trace clock is bpftrace `nsecs`; workload response latency uses `time.monotonic_ns`. The two clock domains are not subtracted from each other. The final censored endpoint is the most recent nominal 10 ms heartbeat from bpftrace; scheduling or tracing delays can make it older than one interval.

## Fixed-nice pilot

After reviewing a completed baseline smoke, the quick fixed-nice configuration runs the same workloads while setting only the batch worker to nice +5. It remains a short pilot, not a repeated comparison study. The runner records its inherited nice value, verifies that the interactive workload keeps that value, and verifies that the batch workload reaches the configured value. It rejects a target that is not higher than the runner's nice value.

Validate the configuration first:

    python3 -m cpu_fairness.cli validate-config configs/fixed_nice_quick.json

Then run it in the Ubuntu guest as the normal user, with the tracer as the only privileged process:

    sudo -v
    set -o pipefail
    python3 -m cpu_fairness.cli smoke \
      --config configs/fixed_nice_quick.json \
      --output-root results | tee /tmp/cpu-fairness-fixed-nice-smoke.json

Expect status completed, a batch process nice value of 5, and an interactive nice value matching policy_application.runner_nice_value. Preserve each run's unique raw and processed output. This pilot does not calculate response-time percentiles or establish a policy effect; those comparisons need a later analysis step and repeated sequential runs.

## Sequential repeated-run pilot

After one baseline and one fixed-nice smoke have completed successfully, use the bounded pilot command to collect up to five baseline/fixed-nice pairs sequentially. It stops on the first failed run and leaves every completed run in its own unique directory. Do not run it concurrently with another experiment.

```bash
sudo -v
set -o pipefail
python3 -m cpu_fairness.cli run-pilot \
  --repeats 3 \
  --output-root results | tee /tmp/cpu-fairness-pilot.json
```

Copy the six run IDs from the JSON output and compare them:

```bash
python3 -m cpu_fairness.cli aggregate-runs \
  results/raw/BASELINE_RUN_1 results/raw/FIXED_NICE_RUN_1 \
  results/raw/BASELINE_RUN_2 results/raw/FIXED_NICE_RUN_2 \
  results/raw/BASELINE_RUN_3 results/raw/FIXED_NICE_RUN_3
```

Aggregation rejects mismatched workload and policy settings, reports run-level means/medians and deterministic bootstrap intervals, and makes no significance claim. Plotting is optional and needs Matplotlib. The simulator reads a completed run and writes hypothetical decisions only:

```bash
python3 -m cpu_fairness.cli plot-runs \
  results/raw/BASELINE_RUN_1 results/raw/FIXED_NICE_RUN_1 \
  --output results/figures/pilot-comparison.png
python3 -m cpu_fairness.cli simulate-run results/raw/BASELINE_RUN_1
```

Both output paths fail rather than overwrite existing files. The simulator does not run as root and does not alter the live scheduler.

## Output to return for Windows-side review

Copy the `run_id` from the CLI output and substitute it below. Send the complete preflight JSON, smoke CLI output, manifest, collector stderr, analysis summary, and a small raw trace sample. Do not send the entire trace unless requested.

Print the per-run metrics summary without modifying the raw or processed artifacts:

    RUN_ID='paste-run-id-here'
    python3 -m cpu_fairness.cli analyze-run "results/raw/$RUN_ID"

The summary reports approximate response-time and turnaround p50/p95 and sample counts, batch throughput, per-TID runnable-wait and CPU-service summaries, and the Delta fairness values when the run contains the required scheduler metadata. Percentiles use nearest-rank. Application timing and scheduler wait use separate clock domains and are not combined.

Interactive request timing is defined as follows:

- `approx_response_time_ns` is the recorded first user-space execution-start timestamp minus the intended release timestamp. It is an approximate user-space response-time measure, not the exact time the kernel first scheduled the task.
- `turnaround_time_ns` is completion minus intended release.
- Per-request CPU service time is not currently measured. Scheduler-derived CPU service is reported per TID and must not be treated as a request's service time.

The analyzer derives both corrected timings from the three preserved monotonic timestamps and checks any explicit corrected fields against those timestamps. Older logs called release-to-completion `response_latency_ns`; the analyzer identifies that legacy field separately, does not use it for corrected metrics, and leaves raw results unchanged. The Delta (Δ) and partitioned ΔB→I calculation is a separate scheduler-clock analysis, distinct from the application request timings.

The per-window Delta output uses only scheduler-clock service and runnable-wait intervals. It omits the initial warm-up window and final partial window, uses the run's CPU affinity and verified `SCHED_OTHER` nice weights, and requires an explicitly unlimited cgroup v2 CPU quota. It reports both directional class deficits only in windows containing active tasks from both classes, without threshold-triggered policy decisions. See [metric definitions](metric_definitions.md) for the equations and current limits. Runs created before scheduler policy, CPU-affinity, and cgroup-quota metadata were added will report Delta as unavailable; their raw files remain usable for the existing metrics.

The default `analyze-run` output includes compact Delta summaries. Add `--include-delta-windows` only when you need the full per-window task records.

```bash
cat /tmp/cpu-fairness-preflight.json
cat /tmp/cpu-fairness-smoke.json
cat "results/raw/$RUN_ID/manifest.json"
cat "results/raw/$RUN_ID/bpftrace.stderr.log"
cat "results/processed/$RUN_ID/analysis.json"
head -n 16 "results/raw/$RUN_ID/scheduler.tsv"
```

If the command fails, also send its exact error text and the run manifest if one was created. Keep raw files so we can diagnose startup, tracepoint field, process identity, event-loss, and reconstruction issues. A successful Windows test run or the previous manual bpftrace test does not replace this guest run.
