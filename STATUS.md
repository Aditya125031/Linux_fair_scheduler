# Project status

Updated: 2026-11-09

## Current state

The core smoke workflow, corrected interactive timing metrics, per-TID scheduler accounting, project-defined Delta analysis, repeat-run tooling, and offline wait-aware simulator are implemented. The latest code additions in this checkout have portable unit coverage, but have not yet been transferred to or exercised in the Ubuntu KVM guest.

The user provided a KVM `analyze-run` result for `quick-smoke-20261109T161240Z-07222b15` with Delta available: 110 post-warmup windows and 95 windows containing both workload classes. This is one smoke run, not a repeated comparison or evidence of policy effects. Earlier reported preflight and smoke outputs remain user-provided; they were not run in this development session.

## Implemented

- Linux preflight checks tracefs roots and scheduler tracepoint formats with noninteractive elevated reads where needed; runner remains unprivileged.
- bpftrace collector startup uses cached noninteractive sudo authentication and performs termination/reaping cleanup.
- Smoke runner writes unique raw and processed run directories, preserves raw traces, manifests, process identities, statuses, and warnings.
- Analysis reconstructs runnable waits and scheduler-observed service, reports corrected approximate response time and turnaround separately, and keeps Python and bpftrace clock domains separate.
- Delta analysis requires verified scheduler-policy, CPU-affinity, and unlimited cgroup CPU-quota metadata; compact summaries are default and per-window records are opt-in.
- `run-pilot` runs bounded baseline/fixed-nice pairs sequentially and stops on failure.
- `aggregate-runs` checks compatible workload and policy configurations and reports descriptive run-level summaries with deterministic bootstrap intervals.
- `plot-runs` creates an optional measured-only comparison plot without overwriting files.
- `simulate-run` emits a bounded, separately labelled hypothetical decision log; it does not alter live Linux scheduling or generate performance outcomes.
- Reproduction and development guides document commands and the KVM validation boundary.

## Validation

- Portable suite in this checkout: **69 passed, 1 skipped**. The skipped check is Windows-only.
- `git diff --check`: passed after the current edits.
- The latest user-provided KVM run exercised the then-current smoke and Delta analyzer. It does **not** validate the new run-pilot, aggregation, plotting, or simulator code.
- No repeated policy comparison, final paper, or full project deliverables have been completed from verified measured data. No raw experiment results were modified.

## Remaining project work

1. Transfer/push these code changes to the guest checkout and run preflight plus a fresh smoke.
2. Review the fresh run's manifest, stderr, raw trace, and compact analysis output.
3. Run at least three sequential baseline/fixed-nice pairs with `run-pilot`, then aggregate and review the result. Start with the short pilot; do not launch the full matrix before checking trace volume and guest disk space.
4. Generate plots from those measured repeated-run summaries and run the simulator separately on measured windows.
5. Prepare the paper, references, and requested source deliverables only after verifying the actual run data. Keep claims and figures tied to those runs.

The full Linux integration and final research deliverables are therefore **not complete**. Portable tests do not establish Linux/eBPF integration.
