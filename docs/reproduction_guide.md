# First smoke experiment: Ubuntu guest checklist

This guide runs one short baseline mixed-workload experiment. It does not run the full matrix. Do not run it on a production host. The Python runner and workloads stay unprivileged; the collector subprocess alone invokes bpftrace through `sudo -n`.

## Bring the updated checkout into the guest

Use the Ubuntu guest's existing project checkout after the Windows changes have been transferred or committed and pulled. From that checkout's root:

```bash
cd ~/Linux-_fair_scheduler
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

## Output to return for Windows-side review

Copy the `run_id` from the CLI output and substitute it below. Send the complete preflight JSON, smoke CLI output, manifest, collector stderr, analysis summary, and a small raw trace sample. Do not send the entire trace unless requested.

```bash
RUN_ID='paste-run-id-here'
cat /tmp/cpu-fairness-preflight.json
cat /tmp/cpu-fairness-smoke.json
cat "results/raw/$RUN_ID/manifest.json"
cat "results/raw/$RUN_ID/bpftrace.stderr.log"
cat "results/processed/$RUN_ID/analysis.json"
head -n 16 "results/raw/$RUN_ID/scheduler.tsv"
```

If the command fails, also send its exact error text and the run manifest if one was created. Keep raw files so we can diagnose startup, tracepoint field, process identity, event-loss, and reconstruction issues. A successful Windows test run or the previous manual bpftrace test does not replace this guest run.
