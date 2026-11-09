# Linux CPU Scheduling Fairness Study

This repository records approximate user-space interactive response time, request turnaround, runnable delay, per-task CPU service, and trace-window Delta (Δ) / partitioned ΔB→I fairness values under mixed interactive and batch workloads. Delta values are emitted only when the run includes verified scheduler-policy and CPU-capacity metadata. The Windows checkout is the development environment. Real scheduler tracing and experiments are run separately in the Ubuntu KVM guest; a Windows test cannot validate eBPF or Linux scheduler behavior.

The Ubuntu KVM guest has completed smoke runs, including a user-reported run where Delta was available for 110 post-warmup windows (95 containing both workload classes). This does not validate the current repeated-run tooling or establish policy effects. Portable code now includes a sequential baseline/fixed-nice pilot, run-level aggregation, optional measured-run plots, and an offline wait-aware simulator. Run the pilot and analysis in the Ubuntu guest before drawing conclusions; see [the reproduction guide](docs/reproduction_guide.md).

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
python3 -m cpu_fairness.cli run-pilot --repeats 3 --output-root results
python3 -m cpu_fairness.cli analyze-run results/raw/PASTE_RUN_ID
python3 -m cpu_fairness.cli aggregate-runs results/raw/RUN_1 results/raw/RUN_2
python3 -m cpu_fairness.cli plot-runs results/raw/RUN_1 results/raw/RUN_2
python3 -m cpu_fairness.cli simulate-run results/raw/PASTE_RUN_ID
```

`run-pilot` collects sequential baseline/fixed-nice pairs and stops on the first failed run. `aggregate-runs` requires matching workload settings and reports run-level summaries with bootstrap confidence intervals; one run is insufficient for an interval. `plot-runs` uses the optional analysis dependencies and writes a measured-only PNG, failing if it would overwrite a file. `simulate-run` writes a separate hypothetical decision log under that run's processed directory and never changes scheduler settings or reports simulated performance outcomes.

Use these only in the Ubuntu guest. Follow [docs/reproduction_guide.md](docs/reproduction_guide.md) for setup and the validation checklist.

## Dependencies

The core runner and trace analysis use the Python standard library. `requirements.txt` installs the project in editable mode and adds pytest for tests. The optional `analysis` extra in `pyproject.toml` provides Matplotlib for plots. Check target guest compatibility before installing it; plotting is optional and does not affect measurement collection.

## Project layout

- `src/cpu_fairness/`: installable Python package, config handling, CLI, and host information.
- `workloads/`, `telemetry/`, `experiment/`, `analysis/`, `policies/`: existing project boundaries for later milestones.
- `configs/`: JSON experiment configurations.
- `tests/`: portable unit tests; Linux integration checks will be separate and explicitly platform-gated.
- `docs/`: development and research methodology documentation.
- `results/raw/` and `results/processed/`: reserved for distinct raw and derived data. Raw runs must not be overwritten.

See [docs/development_guide.md](docs/development_guide.md) for Windows development, test commands, and the Linux validation boundary. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for milestone objectives and acceptance checks.
