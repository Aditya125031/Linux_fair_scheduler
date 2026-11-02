# Project status

Updated: 2026-11-02

## Current phase

**First end-to-end smoke implementation is ready for Ubuntu guest validation.** No Linux integration test or real experiment has been run from this Windows session.

## Environment facts

- Development and portable tests are running on Windows.
- The tested interpreter is Windows CPython 3.12.0. The first `python` on PATH is a separate MSYS CPython 3.12.12 without pip.
- The user reports the experimental guest is Ubuntu 26.04.1 LTS, kernel 7.0.0-42-generic, Python 3.14.4, bpftrace 0.25.0, two vCPUs, and approximately 3.3 GiB usable RAM. A manual `sched_wakeup` smoke test with sudo has previously succeeded there.
- No Linux command, bpftrace script, or guest test was executed in this Windows session. The prior manual smoke is user-reported evidence only and does not validate this collector.
- Existing `batch_results.csv` and `interactive_results.csv` were not modified. Their provenance remains unknown.

## Completed in this milestone

- Linux-only `preflight` CLI and `scripts/preflight.sh`: reports OS/kernel/Python/bpftrace versions; reads `sched_wakeup` and `sched_switch` tracefs `format` files and checks required fields; checks BTF, tracefs, cgroup v2/controllers, runner UID, and cached noninteractive sudo ability to invoke bpftrace.
- Workloads: periodic interactive bursts logged as JSONL and CPU-bound batch work logged as JSON. Each reports its PID/TGID and native TID. The Linux runner verifies one `/proc/<pid>/task` entry and correlates that TID with the workload.
- Collector: packaged `scheduler.bt` captures raw `sched_wakeup` and `sched_switch` TSV records, with READY emitted from the trailing interval probe, `nsecs` timestamps, explicit `-1` missing markers, stderr, and an END timestamp from a 10 ms heartbeat. Runtime attachment and timing remain unverified until the guest run.
- Runner: `smoke` starts tracing before the workloads, remains unprivileged, invokes only the tracer through `sudo -n`, preserves unique raw/processed run directories and a manifest, and fails instead of reporting success if no complete target wait is reconstructed.
- Analysis: strict TSV parsing, runnable-wait reconstruction for wakeup and runnable preemption, duplicate-wakeup warnings, censored final waits, and scheduler-observed CPU service with incomplete intervals flagged.
- Clock handling: request latency uses only Python monotonic timestamps; wait and CPU service use only bpftrace `nsecs`. No cross-clock subtraction is performed.
- Reproduction and development docs updated. No full matrix or additional policy was implemented.

Against `IMPLEMENTATION_PLAN.md`, the portable implementation portions of Milestones 3–5 are now present. Their guest-side acceptance checks remain pending: collector attachment/output, real task identity, event loss/order behavior, and the end-to-end smoke evidence.

## Validation status

- **Windows portable/synthetic tests:** 26 test methods passed under CPython 3.12.0, covering config/CLI, workload logs, trace parsing, synthetic wake/preemption/duplicate/incomplete cases, OS/tracepoint-format parsing, and the Windows safety guard.
- **Windows CLI:** config validation passed. `preflight --json` returned exit code 2 with `linux_platform: false`; this is the expected safe Windows result, not a Linux failure or pass.
- **Windows packaging:** editable install succeeded; a wheel build succeeded and included `cpu_fairness/telemetry/scheduler.bt`.
- **Ubuntu preflight, bpftrace script compile/attach, collector readiness/stop, real workload identity, event loss behavior, and end-to-end smoke:** pending user execution in the guest. Do not mark these passed until their actual output is reviewed.
- **Experimental measurements:** none produced by this milestone.

## Next action

Transfer the updated checkout to the Ubuntu guest, run the exact checklist in `docs/reproduction_guide.md`, and return the preflight JSON, smoke CLI output, raw-run manifest, bpftrace stderr, processed analysis summary, and the requested short raw TSV sample. Then fix any integration issues revealed by that evidence before expanding the experiment design.
