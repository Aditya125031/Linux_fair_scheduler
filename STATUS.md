# Project status

Updated: 2026-11-06

## Current phase

**Baseline and fixed-nice guest pilots completed; per-run metrics implemented.** Guest results below were provided by the user; they were not run in this development session.

## Environment facts

- Portable tests are run in the development environment; use the Ubuntu guest for Linux scheduler integration and policy experiments.
- The user reports the experimental guest is Ubuntu 26.04.1 LTS, kernel 7.0.0-42-generic, Python 3.14.4, bpftrace 0.25.0, two vCPUs, and approximately 3.3 GiB usable RAM. A manual `sched_wakeup` smoke test with sudo has previously succeeded there.
- User-provided Ubuntu KVM smoke: run `quick-smoke-20261106T114311Z-33ec16c9`, commit `aa79b86c19d32d1d0134c4d7fa6dda677fff31d7`, status completed; collector return code 0; both workloads exited 0; 798,683 trace records and 42,892 complete reconstructed waits; no warnings reported. A manual raw-trace/derived-wait comparison confirmed one 97,170 ns runnable-preemption wait. Absence of warnings does not establish absence of event loss.
- User-provided baseline repeat: run `quick-smoke-20261106T120214Z-6b9a3899`, commit `7e11866a6183386dca4e82c72d72118262f602d7`, completed with both nice values 0 and 410,879 trace records.
- User-provided fixed-nice pilot: run `quick-fixed-nice-20261106T120350Z-78537623`, same commit, completed with runner/interactive nice 0, batch nice 5, and 917,536 trace records. This is one fixed-nice run, not evidence of a policy effect.
- Existing `batch_results.csv` and `interactive_results.csv` were not modified. Their provenance remains unknown.

## Completed in this milestone

- Linux-only `preflight` CLI and `scripts/preflight.sh`: reports OS/kernel/Python/bpftrace versions; reads `sched_wakeup` and `sched_switch` tracefs `format` files and checks required fields; checks BTF, tracefs, cgroup v2/controllers, runner UID, and cached noninteractive sudo ability to invoke bpftrace.
- Workloads: periodic interactive bursts logged as JSONL and CPU-bound batch work logged as JSON. Each reports its PID/TGID and native TID. The Linux runner verifies one `/proc/<pid>/task` entry and correlates that TID with the workload.
- Collector: packaged `scheduler.bt` captures raw `sched_wakeup` and `sched_switch` TSV records; the collector preserves valid event rows emitted before READY, uses `nsecs` timestamps and explicit `-1` markers, retains stderr, and records an END timestamp from a 10 ms heartbeat. The user-provided run verified collector start/stop in the guest.
- Runner: `smoke` starts tracing before workloads, stays unprivileged, invokes only the tracer through `sudo -n`, preserves unique raw/processed run directories and a manifest, and fails if no complete target wait is reconstructed. It supports baseline and fixed-nice configuration, and records/verifies runner, interactive, and batch nice values.
- Per-run analysis: `analyze-run` reports nearest-rank interactive response latency p50/p95 with sample count, batch throughput, and per-TID runnable-wait and observed CPU-service summaries. Clock domains remain separate.
- Analysis: strict TSV parsing, runnable-wait reconstruction for wakeup and runnable preemption, duplicate-wakeup warnings, censored final waits, and scheduler-observed CPU service with incomplete intervals flagged.
- Clock handling: request latency uses only Python monotonic timestamps; wait and CPU service use only bpftrace `nsecs`. No cross-clock subtraction is performed.
- Reproduction and development docs include the fixed-nice pilot workflow. No full matrix or wait-aware simulator was implemented.

Against `IMPLEMENTATION_PLAN.md`, baseline and fixed-nice guest pilots have completed. Repeated runs, cross-run aggregation, the bounded simulator, and full research analysis remain outstanding.

## Validation status

- **Portable/unit suite:** 43 tests passed, 1 platform-guard test skipped in the development environment.
- **Ubuntu KVM baseline smoke:** user-provided manifest completed. Preflight, tracepoint field checks, collector READY/stop, workload identities, parsing, and at least one reconstructed runnable wait were exercised together.
- **Fixed-nice guest pilot:** user-provided completed manifest verifies batch nice 5 and interactive nice 0. Replication is still needed.
- **Experimental measurements:** none produced by this milestone.

## Next action

Run `analyze-run` on the existing completed guest runs, then collect sequential baseline and fixed-nice repeats until there are at least three runs per policy. Review stderr, warnings, workload samples, and disk usage before expanding the matrix. Do not make policy claims from the current single fixed-nice pilot.
