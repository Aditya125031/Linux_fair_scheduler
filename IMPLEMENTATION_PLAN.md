# Implementation plan

## Goal and boundary

Deliver a small, reproducible Linux scheduler study within seven days. The first success criterion is one real, trace-backed mixed-workload run comparing the default scheduler with fixed batch `nice +5`, followed by valid parsed wait/CPU-service data and a basic report. Build the wait-aware policy as a bounded offline simulator after this path works. Do not implement `sched_ext` or a live controller. Do not start the full 90-run matrix until a pilot is stable and the team has time and disk capacity.

## Proposed architecture

```text
JSON configs + CLI
        |
        v
Unprivileged experiment runner ---- system/environment manifest
        |                 |
        |                 +---- interactive process (JSONL request records)
        |                 +---- batch worker processes (completion summaries)
        |
        +---- narrowly privileged bpftrace collector
                         |
                 immutable raw trace + stderr/status
                         |
                 parser + schema validation
                         |
             wait-episode and CPU-service reconstruction
                         |
         latency/throughput/fairness/statistical analysis
                         |
             measured CSV/JSON + plots/report

Measured observations ---> separate bounded wait-aware simulator ---> decision log
```

Keep the current top-level folders initially to avoid an unnecessary repository-wide move: `workloads/` owns workload programs; `telemetry/` owns bpftrace, collector and parser; `experiment/` owns orchestration and manifests; `analysis/` owns reconstruction, metrics, aggregation and plots; `policies/` owns baseline/fixed-nice configuration and simulator; `configs/` owns JSON; `tests/` owns portable synthetic tests and Linux-only integration tests; `docs/` and `paper/` own research deliverables. Add a package/CLI foundation only as needed, with clearly documented import/run commands. The runner remains ordinary-user Python; only its collector child may use `sudo`.

### Data contracts to freeze before module work

1. **Raw scheduler record:** one machine-readable record per event, monotonic nanosecond timestamp, event name, numeric PID/TID identity, CPU, and explicit nullable event-specific fields (wake target/priority; switch prev/next IDs/state/priorities; migration source/destination; exit; scheduler-reported wait). Keep original bytes and stderr immutable; parser errors include line number and raw line. Inspect tracepoint formats at runtime and enable only supported probes.
2. **Interactive request JSONL:** run/workload ID, request ID, intended release monotonic timestamp recorded before sleeping, observed execution-start timestamp, completion timestamp, burst/config values, and completion status. Response latency is completion minus intended release. State clearly that application monotonic timestamps and kernel trace timestamps are separate clock domains unless an explicit alignment method is implemented; do not subtract them blindly.
3. **Batch worker summary:** run ID, worker ID, PID/TID identity, nice value, configured unit, completed units, elapsed wall time, and exit/completion status. Throughput is completed units divided by the defined measurement interval.
4. **Per-run manifest:** unique run ID/directory, Git revision, kernel/OS/CPU/vCPU/memory/virtualization/cgroup/tool versions, configuration/seed, process IDs and nice values, collector times/status, event counts, warnings/loss/incomplete indicators, workload statuses, and output paths. Raw output is never overwritten.
5. **Analysis outputs:** reconstructed wait episodes with complete/censored flag and source; per-task CPU service with trace-window completeness caveat; run-level latency, throughput, context-switch/migration counts; fairness only for comparable equal-demand batch workers. Mark synthetic and simulated outputs in separate locations and schemas.

## Seven-day ordered milestones

Each milestone is intentionally small. A milestone is accepted only when its stated checks pass; Linux-only checks must be run in the actual Ubuntu guest.

### 1. Freeze contracts and guest preflight (Day 1)

- **Objective:** establish actual guest capabilities and interfaces before parallel implementation; resolve tracepoint fields, package availability, output storage, and privilege workflow.
- **Files/modules:** `docs/architecture.md`, `docs/methodology.md`, `docs/metric_definitions.md`, `docs/development_guide.md`, `configs/*.json`, `tests/fixtures/`; team interface note/`CONTRIBUTING.md`.
- **Dependencies:** repository access in the guest; Python/pip/Git; bpftrace and tracefs/BTF where applicable.
- **Acceptance:** capture actual guest OS/kernel/Python/bpftrace, CPU/memory/disk, cgroup mode, tracepoint formats and privileges; confirm tracepoint availability and whether `sched_stat_wait` is enabled; agree on event and workload schemas; preserve current CSVs and establish their provenance as unknown until verified.
- **Gate:** if a required tracepoint or bpftrace output capability is absent, document a narrow fallback or adjust methodology before building on it.

### 2. Portable foundation and synthetic tests (Day 1–2)

- **Objective:** establish configuration validation, output layout, manifest shape, and pure-Python logic that can be developed on Windows.
- **Files/modules:** package/CLI and config/system-info/manifest modules; `configs/`; `.gitignore`; `tests/test_config.py`, `tests/test_manifest.py`, fixtures; dependency metadata only after compatibility check.
- **Dependencies:** Milestone 1 contracts; Windows Python 3.12.12 is available here, while target Python 3.14.4 must be checked separately.
- **Acceptance:** valid/invalid JSON cases have explicit behavior; manifests can be generated without Linux calls; unique run-directory creation refuses collisions; portable tests pass on Windows; Python 3.14 package compatibility is recorded. No Linux behavior is inferred from these checks.

### 3. Small workload pair and one end-to-end smoke path (Day 2–3)

- **Objective:** get the smallest real experiment running before broad analysis/features: one periodic interactive process and one or two batch processes with identifiable PIDs and bounded duration.
- **Files/modules:** replace/refactor `workloads/interactive.py`, `workloads/batch.py`; add workload config; add minimal `experiment/runner.py`; run JSONL and worker summary schema.
- **Dependencies:** Milestone 2; guest process-control behavior and clock semantics.
- **Acceptance:** interactive records intended release before sleep and records execution-start/completion; batch uses independent CPU-bound processes, not threads; runner captures each PID, exit status, nice value, and stops children on interruption; short workload-only smoke run produces parseable records. Test on Windows for portable workload/log behavior and on Ubuntu for Linux process/nice behavior.

### 4. bpftrace collector and raw event preservation (Day 3–4)

- **Objective:** collect a small verified stream from the actual guest, with raw output and errors retained.
- **Files/modules:** `telemetry/scheduler.bt`, `telemetry/collector.py`, preflight/smoke CLI or `scripts/preflight.sh`, `scripts/smoke_test.sh`; raw-run manifest fields.
- **Dependencies:** Milestone 1 tracepoint inspection; Milestone 3 PID lifecycle; sudo available for tracer only.
- **Acceptance:** collector checks supported tracepoints/fields, starts before workloads, confirms startup, captures required supported events in machine-readable records with nanosecond timestamps, writes stderr/status/start-stop metadata, and terminates cleanly. The guest smoke run must show workload PIDs in real trace events and nonempty valid output; record possible loss warnings. Windows can test command construction and parsers only, never collector success.

### 5. Parser, wait reconstruction, and CPU service (Day 4–5)

- **Objective:** derive defensible per-task runnable waits and CPU service, including preemption rather than wakeup-only delays.
- **Files/modules:** `telemetry/parser.py`; `analysis/wait_episodes.py`, `analysis/cpu_accounting.py`; `tests/test_trace_parser.py`, `tests/test_wait_episodes.py`, `tests/test_cpu_accounting.py`, synthetic fixtures.
- **Dependencies:** Milestone 4 stable schema; monotonic event order and identity decision.
- **Acceptance:** synthetic wake 100→schedule 350 yields 250 ns; runnable switch-out 500→schedule 800 yields 300 ns; tests cover duplicate wakeups, sleep-vs-runnable switch state, exits, PID/task state cleanup, migrations, out-of-order input (sort analysis copy; preserve raw), malformed records, trace-window incomplete service, and censored ending waits. Compare `sched_stat_wait` independently where present. Guest pilot produces plausible nonempty complete/censored records; document event loss and thread/TID semantics.

### 6. Measured A/B experiment and core metrics (Day 5–6)

- **Objective:** run repeatable baseline and fixed batch nice comparison; produce the first valid measured result and basic analysis.
- **Files/modules:** `policies/baseline.py`, `policies/fixed_nice.py`; `configs/experiment_matrix.json`; runner/resume logic; `analysis/metrics.py`, `analysis/fairness.py`, `analysis/aggregation.py`, one basic plot/report; `tests/test_metrics.py`, `tests/test_fairness.py`, runner tests.
- **Dependencies:** Milestones 3–5 and successful guest smoke; verified `nice +5` behavior; adequate free disk.
- **Acceptance:** unique non-overwriting run dirs; a short pilot is reviewed for trace volume and workload shape; sequential runs compare A (default) and B (batch +5), each manifest records actual environment/PIDs/nice/status; response percentiles report sample count, throughput definition is consistent, Jain index only covers comparable batch workers; failures and missing data are not reported as success. Obtain repeat runs only after pilot stability. Simulator output is not mixed into measured results.

### 7. Bounded simulator, repeatability, and paper-ready outputs (Day 6–7)

- **Objective:** finish the offline wait-aware demonstration and minimum honest project/research handoff; expand experiments only if time and stability permit.
- **Files/modules:** `policies/wait_aware_simulator.py`; `configs/policies.json`; `tests/test_policies.py`; `analysis/plots.py`; `docs/reproduction_guide.md`, `docs/limitations.md`, `CONTRIBUTING.md`; `paper/main.tex`, `paper/references.bib`, paper README and packaging scripts as time allows.
- **Dependencies:** real measured trace sample from Milestone 6; verified academic references; available LaTeX toolchain for PDF.
- **Acceptance:** simulator has threshold, bounded boost, aging and cooldown, emits decision logs only, and tests max bounds/starvation safeguards using synthetic input; plots are generated only from actual processed runs and labelled by source; at least five references are independently verified; paper keeps explicit result placeholders until measurements exist; reproduction commands work in guest. Run a reduced matrix before considering the suggested 90 runs. Package sources without caches/credentials/large temporary traces.

## Test and validation boundary

| Check | Windows development machine | Ubuntu KVM guest |
|---|---|---|
| JSON/config validation, manifest schema, parsing of saved synthetic trace, wait/service reconstruction, metrics/fairness, simulator bounds | Yes, subject to Python/package support | Yes |
| Workload record schema and deterministic pure-Python workload logic | Yes | Yes |
| Python 3.14 and dependency compatibility | Not established here (Windows Python is 3.12.12) | Verify against guest Python 3.14.4 |
| Linux preflight, tracefs/BTF/tracepoint format, bpftrace attach/output/loss behavior | No | Required |
| Real scheduler wait and CPU service validation, event identity/order, process lifecycle | No | Required |
| Actual `nice` policy and cgroup behavior | No | Required |
| End-to-end smoke, quick/pilot/full experiments, final reproducibility | No | Required |
| IEEE PDF compilation | Only if a suitable Windows LaTeX installation exists; none found on PATH | Verify/install/use a suitable toolchain if permitted |

Use platform-aware integration tests that skip with a clear reason outside Linux or when required tools/capabilities are missing. A skip is not a pass for Linux validation. The final claim of a working project requires a successful Ubuntu guest smoke run and saved evidence from that guest.

## Main technical risks, ambiguities, and conflicts

1. **Environment/version mismatch:** the spec reports Ubuntu 26.04.1 and Linux 7.0, while this workspace is Windows and the guest is inaccessible here. Verify guest reality; do not assume the listed versions or support Python 3.14 packages without checking.
2. **Clock domains:** request latency uses Python monotonic timestamps while trace timestamps use kernel/bpftrace monotonic time. They may be related but must not be compared across domains without a validated offset/alignment method. Use each clock for its own metric otherwise.
3. **Trace identity and PID reuse:** scheduler tracepoint `pid` often identifies a task/thread (TID), while user-facing process IDs may be TGIDs. Track the same identity consistently and consider process start/exit plus PID reuse; process names are not identities.
4. **Wait semantics:** `sched_switch` prev state encoding and wakeup/switch sequencing need runtime/schema verification. Duplicate wakeups, preemption, blocked tasks, migrations, tracing that starts mid-run, and event loss can corrupt reconstructed intervals. Keep incomplete intervals explicit and test state transitions synthetically.
5. **Tracepoint variability and permission:** formats vary by kernel; `sched_stat_wait` availability/use may depend on kernel config. `kernel.unprivileged_bpf_disabled=2` and high perf paranoia in the spec imply privileged tracing. Use sudo only for the tracer and test its launch/termination/output handling in guest.
6. **Measurement overhead and resource limits:** two vCPUs, about 3.3 GiB RAM, and limited disk make a 90-run matrix plus verbose raw trace potentially too costly. Sequential short pilot, bounded trace duration, disk checks, and reduced matrix are essential. Do not run concurrent experiments.
7. **Fairness interpretation:** Jain fairness across interactive and batch classes is not meaningful without justified equal demand. Begin with equal-demand batch workers; document zero service and incomplete runs. Fixed nice changes the policy but does not equalize CPU or make a causal claim by itself.
8. **Interactive workload semantics:** current code measures CPU burst duration from actual work start and uses threads; this omits time waiting for intended arrivals and is unsuitable as the specified response latency. Schedule release times first, record before sleep, and use monotonic clocks.
9. **CPU service bounds:** switch trace intervals estimate scheduled wall-time, not necessarily on-core execution under every virtualization/clock/loss condition. Mark intervals crossing trace boundaries as incomplete and describe this as scheduler-observed service estimate.
10. **Scope/time conflict:** the spec asks for robust telemetry, 90 measurements, eight plots, simulator, docs, four deliverables, literature review, and a six-page paper in seven days. Prioritize a valid smoke and small A/B pilot; expand only after the measurement pipeline is trustworthy. Simulator is hypothetical and cannot supply performance improvements.
11. **Dependency/Python compatibility:** NumPy/Pandas/Matplotlib/pytest support for target Python 3.14 must be checked before selecting pins. Keep core parsing/runner logic on stdlib where possible and do not replace guest system Python.
12. **Paper and result integrity:** no real measurements or verified sources were established in this inspection. Existing CSV provenance is unknown. Do not use either as results until provenance/schema are checked; leave paper results as placeholders until guest experiments finish.
13. **Spec tension:** the detailed first-task request here is planning-only, while the specification’s final sections request implementation after planning. This task explicitly stops before implementation, so implementation remains a later step.

## Seven-day execution order (team)

Freeze schemas first, then split work by ownership: workload/runner; telemetry/parser/reconstruction; metrics/tests; simulator/docs/paper. Integrate against the same fixtures and schema daily. One person should own the Ubuntu guest run and raw-data preservation; do not let parallel branches invent alternate event or metric contracts.
