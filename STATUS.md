# Project status

Updated: 2026-11-15

## Current state

The core smoke workflow, corrected interactive timing metrics, per-TID scheduler accounting, project-defined Delta analysis, repeat-run tooling, and offline wait-aware simulator are implemented. The KVM has pulled commit `51fa786` and the user successfully generated `results/figures/pilot-comparison.svg` from six completed runs. The latest local additions expand graph diagnostics and have not yet been transferred or exercised in the KVM.

The user provided a KVM `analyze-run` result for `quick-smoke-20261109T161240Z-07222b15` with Delta available: 110 post-warmup windows and 95 windows containing both workload classes. This is one smoke run, not a repeated comparison or evidence of policy effects. Earlier reported preflight and smoke outputs remain user-provided; they were not run in this development session.

## Implemented

- Linux preflight checks tracefs roots and scheduler tracepoint formats with noninteractive elevated reads where needed; runner remains unprivileged.
- bpftrace collector startup uses cached noninteractive sudo authentication and performs termination/reaping cleanup.
- Smoke runner writes unique raw and processed run directories, preserves raw traces, manifests, process identities, statuses, and warnings.
- Analysis reconstructs runnable waits and scheduler-observed service, reports corrected approximate response time and turnaround separately, and keeps Python and bpftrace clock domains separate.
- Delta analysis requires verified scheduler-policy, CPU-affinity, and unlimited cgroup CPU-quota metadata; compact summaries are default and per-window records are opt-in.
- `run-pilot` runs bounded baseline/fixed-nice pairs sequentially and stops on failure.
- `aggregate-runs` checks compatible workload and policy configurations and reports descriptive run-level summaries with deterministic bootstrap intervals.
- `run-nice-sweep` compares baseline with up to three fixed nice levels sequentially.
- `plot-runs` creates a measured-only SVG with response p95/p99, turnaround, throughput, and Delta summaries; each fixed nice value is a distinct group.
- Local uncommitted work adds `plot-diagnostics` for response and wait CDFs, per-TID service, Delta-window distributions, and response/throughput trade-offs.
- `simulate-run` emits a bounded, separately labelled hypothetical decision log; it does not alter live Linux scheduling or generate performance outcomes.
- Reproduction and development guides document commands and the KVM validation boundary.

## Validation

- Portable suite before the latest local graph-diagnostics edits: **69 passed, 1 skipped**. The skipped check is Windows-only. The suite has not been rerun for the local graph-diagnostics code.
- `git diff --check` and current CLI help were checked for commit `51fa786`; local diagnostic-graph edits still need review.
- User-provided KVM validation confirms six runs aggregated and the SVG comparison plot generated successfully under `51fa786`. No KVM validation has occurred for the local diagnostic graphs.
- No repeated policy comparison, final paper, or full project deliverables have been completed from verified measured data. No raw experiment results were modified.

## Remaining project work

1. Validate local `plot-diagnostics` changes with portable tests and review the generated SVG layouts.
2. If accepted, push the additions and generate diagnostic graphs from the six existing KVM runs.
3. To chart different batch nice levels, run a bounded `run-nice-sweep` and aggregate/plot the new run IDs with the existing +5 runs.
4. A graph comparing p95/p99 across increasing batch-worker contention still requires runner support for multiple batch workers; the current smoke runner is restricted to one batch worker.
5. Prepare the paper, references, and source deliverables only after verifying actual run data. Keep claims and figures tied to those runs.

The full Linux integration and final research deliverables are therefore **not complete**. Portable tests do not establish Linux/eBPF integration. The wait-aware policy remains simulated, with no measured performance outcomes.
