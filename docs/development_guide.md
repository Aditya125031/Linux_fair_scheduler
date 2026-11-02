# Development guide

## Development and experiment environments

Develop portable Python code on Windows. The separate Ubuntu 26.04.1 KVM guest is the only environment for real Linux scheduler tracing and experiments. The guest is reported to have kernel 7.0.0-42-generic, bpftrace 0.25.0, two vCPUs, and about 3.3 GiB usable RAM. Treat these as the team's supplied environment facts and recheck them with guest preflight before a run.

Do not run bpftrace or Linux-only commands through PowerShell. A Windows test can validate configuration logic, parsers against saved synthetic data, metric calculations, and portable Python behavior. It cannot show that a tracepoint exists, bpftrace attaches, scheduler events are collected, or Linux nice behavior works.

## Install on Windows

From PowerShell at the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

This project requires Python 3.11 or newer. The current Windows Python may be a different version from the Ubuntu guest. Record the interpreter version when reporting test results. If pip cannot reach the package index, use an approved package source or prepare dependencies separately; do not report unrun tests as passing.

On the inspected Windows host, the first `python` on `PATH` is an MSYS build without pip. Use an installed CPython executable instead and verify both `--version` and `-m pip --version` before creating the virtual environment.

## Run the current checks

```powershell
python -m pytest
python -m cpu_fairness.cli info
python -m cpu_fairness.cli validate-config configs/quick.json
```

Current tests also run without pytest because they use the standard-library unittest API:

```powershell
python -m unittest discover -s tests -v
```

The current tests cover configuration and CLI behavior, workload log records, trace parsing, synthetic wait/service reconstruction, tracepoint-format parsing, and the Windows safety guard. They do not attach to Linux probes or perform experiments. Synthetic timestamps are test fixtures, not measurements.

## Configuration contract

The initial config uses `schema_version: 1` and has an experiment ID, positive duration, interactive arrival interval and burst size, batch worker count and unit size, and a policy. Supported policy types in this foundation are `baseline` and `fixed_nice`; the latter accepts batch nice values from 0 through 19. Validation does not launch or alter any process. The wait-aware simulator will use a separate configuration and produce simulated decisions only.

## Linux-only validation still required

Run these checks inside the Ubuntu guest before treating the smoke path as validated:

1. Preflight actual OS/kernel/Python/bpftrace versions, resources, cgroup mode, tracefs/BTF, scheduler tracepoint availability and fields, and permissions.
2. Confirm the manually tested `sched_wakeup` path still works with `sudo`, then verify each additional supported tracepoint and machine-readable output.
3. Run the end-to-end smoke with the Python runner unprivileged and only the tracer elevated. Preserve raw trace, stderr, exit status, timing, and warnings.
4. Validate real task IDs, event ordering/loss, runnable-wait reconstruction, and CPU-service estimates.
5. Preserve the output files and return the preflight JSON, run manifest, bpftrace stderr, processed analysis summary, and a short raw trace sample. Keep this run sequential and inspect free disk before considering later experiments.

The preflight, collector, workloads, and smoke runner are implemented but remain unvalidated on Linux until the checklist in `reproduction_guide.md` is run inside the Ubuntu guest. The team's previous manual `sched_wakeup` smoke test is user-reported environment evidence, not a test of this implementation.
