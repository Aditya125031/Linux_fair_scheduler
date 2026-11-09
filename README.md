# Linux CPU Scheduling Fairness Study

This repository records approximate user-space interactive response time, request turnaround, runnable delay, and per-task CPU service under mixed interactive and batch workloads. The separate Delta (Δ) / partitioned ΔB→I fairness calculation is not produced by the current per-run analyzer. The Windows checkout is the development environment. Real scheduler tracing and experiments are run separately in the Ubuntu KVM guest; a Windows test cannot validate eBPF or Linux scheduler behavior.

The baseline and one fixed-nice pilot have completed in the Ubuntu KVM guest, including preflight, the bpftrace collector, both workloads, and wait/service reconstruction. The fixed-nice run verified batch nice +5 while interactive remained at nice 0. Per-run latency, throughput, wait, and service summaries are available; repeated runs and aggregation are still needed before drawing policy conclusions.

## Current setup

Use Python 3.11 or newer. From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use a CPython interpreter that includes pip. On the inspected Windows host, the first `python` on `PATH` is an MSYS build without pip; an installed CPython 3.12 is available separately. Check `python --version` and `python -m pip --version` before creating the environment.

On Linux, activate the virtual environment with `source .venv/bin/activate` and run `python -m pip install -r requirements.txt`.

Show information about the current host:

```powershell
python -m cpu_fairness.cli info
```

Validate the sample configuration:

```powershell
python -m cpu_fairness.cli validate-config configs/quick.json
```

Run the current tests with pytest after installing the test extra, or use the standard-library runner without pytest:

```powershell
python -m pytest
python -m unittest discover -s tests -v
```

The installed `cpu-fairness` command provides the same CLI. The `info` command is read-only and does not probe bpftrace, alter host settings, or create the output directory.

The Linux-only commands are:

```bash
python3 -m cpu_fairness.cli preflight --json
python3 -m cpu_fairness.cli smoke --config configs/quick.json --output-root results
python3 -m cpu_fairness.cli analyze-run results/raw/PASTE_RUN_ID
```

Use these only in the Ubuntu guest. Follow [docs/reproduction_guide.md](docs/reproduction_guide.md) for setup and the validation checklist.

## Dependencies

The core foundation uses only the Python standard library. `requirements.txt` installs the project in editable mode and adds pytest for tests. The optional `analysis` extra in `pyproject.toml` lists NumPy, Pandas, and Matplotlib for a later analysis milestone; those packages are not needed for the current foundation. Check the target guest's Python/package compatibility before installing them there.

## Project layout

- `src/cpu_fairness/`: installable Python package, config handling, CLI, and host information.
- `workloads/`, `telemetry/`, `experiment/`, `analysis/`, `policies/`: existing project boundaries for later milestones.
- `configs/`: JSON experiment configurations.
- `tests/`: portable unit tests; Linux integration checks will be separate and explicitly platform-gated.
- `docs/`: development and research methodology documentation.
- `results/raw/` and `results/processed/`: reserved for distinct raw and derived data. Raw runs must not be overwritten.

See [docs/development_guide.md](docs/development_guide.md) for Windows development, test commands, and the Linux validation boundary. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for milestone objectives and acceptance checks.
