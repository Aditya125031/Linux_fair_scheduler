\# MASTER PROJECT PROMPT — Operating Systems Assignment 2



\## Project Title



\*\*eBPF-Based Detection and Mitigation of CPU Scheduling Unfairness Under Mixed Workloads\*\*



You are acting as the lead software engineer, systems researcher, Linux/eBPF developer, and technical documentation assistant for a four-member undergraduate Operating Systems project.



Your responsibility is to help us build a complete, working, reproducible experimental project and prepare its research-paper deliverables.



Do not treat this as a generic programming exercise. The project must have a technically sound measurement methodology, reliable experimental results, reproducible scripts, and clear documentation.



We are beginners in Linux kernel observability and eBPF. Therefore, write understandable code, explain important implementation decisions, and avoid unnecessary complexity.



\---



\# 1. PROJECT OBJECTIVE



We want to investigate whether latency-sensitive interactive processes experience unfair CPU scheduling delays when they compete against CPU-intensive batch processes.



We want to:



1\. Generate repeatable mixed workloads consisting of interactive and batch tasks.

2\. Observe Linux scheduler events using eBPF/bpftrace.

3\. Measure how long tasks remain runnable before receiving CPU time.

4\. Measure interactive response latency and batch throughput.

5\. Calculate CPU service distribution and appropriate fairness metrics.

6\. Compare different scheduling configurations.

7\. Study a bounded wait-aware scheduling policy.

8\. Generate graphs and analyse trade-offs between responsiveness, fairness, and throughput.

9\. Produce a reproducible experiment package.

10\. Prepare a six-page IEEE-style research paper.



The central research question is:



\*\*How does competition from CPU-intensive batch workloads affect the runnable delay, response latency, and CPU service fairness of interactive tasks, and how do alternative scheduling configurations change these outcomes?\*\*



The project should prioritise rigorous measurement and analysis over implementing a completely new kernel scheduler.



\# 2. IMPORTANT IMPLEMENTATION DECISIONS



Follow these decisions unless a genuine technical limitation requires an explicitly documented change.



\### 2.1 Do not implement sched\_ext



Do not attempt to write a custom Linux kernel scheduler using sched\_ext.



It is optional for our assignment and is too risky for our available development time.



Our core project is based on:



\- eBPF-based scheduler observability.

\- Repeatable mixed workloads.

\- Scheduler wait-time reconstruction.

\- Measured policy comparisons.

\- Fairness and performance analysis.

\- A wait-aware policy simulator.



\### 2.2 Scheduling configurations



Implement these configurations:



\*\*Configuration A — Default Linux scheduler\*\*



All workload processes use their normal default scheduling priority.



This is our baseline.



\*\*Configuration B — Fixed batch deprioritisation\*\*



Interactive processes retain their default nice value.



Batch processes run with a configurable higher nice value, initially +5.



This tests whether lowering the relative scheduling priority of batch workloads improves interactive responsiveness.



Do not attempt to give interactive processes negative nice values by default because that may require additional privileges.



\*\*Configuration C — Wait-aware policy simulator\*\*



Implement a bounded wait-aware policy simulator that examines measured scheduler waiting-time data and generates hypothetical scheduling-policy decisions.



The simulator should demonstrate concepts such as:



\- Detecting excessive runnable waiting time.

\- Applying a bounded boost request.

\- Preventing unlimited priority increases.

\- Applying aging.

\- Enforcing maximum boost levels.

\- Recording policy decisions.



Important: The simulator does not modify the real Linux scheduler. Its outputs must be labelled as simulated decisions, not actual measured performance improvements.



Do not combine simulated results with measured scheduler results.



An actual cgroup-based dynamic controller may be considered later only if its feasibility and permission requirements are verified and the core project is already working.



\### 2.3 Scope control



Do not add:



\- A web application.

\- A frontend or dashboard.

\- A database.

\- Machine-learning models.

\- Cloud infrastructure.

\- GPU requirements.

\- Unnecessary microservices.

\- Custom kernel modules.

\- sched\_ext implementation.



A Python command-line project, bpftrace scripts, CSV/JSON output, and research-paper deliverables are sufficient.



\---



\# 3. ACTUAL DEVELOPMENT AND EXPERIMENTAL ENVIRONMENT



The code may be developed using Codex on Windows or another development operating system.



However, the actual scheduler experiments and eBPF tracing must run inside our Ubuntu Linux guest.



Do not assume that Windows can execute Linux eBPF tracing.



\## Target experimental machine



Physical host:



\- Operating system: Ubuntu 24.04.5 LTS.

\- Virtualisation: KVM/QEMU.

\- CPU: Intel Core i5-9300H @ 2.40 GHz.

\- Physical cores: 4.

\- Logical CPUs: 8.

\- RAM: approximately 15 GiB.



Ubuntu guest:



\- Operating system: Ubuntu 26.04.1 LTS.

\- Kernel: Linux 7.0.0-42-generic.

\- Architecture: x86\_64.

\- Virtualisation: KVM.

\- Allocated vCPUs: 2.

\- Effective CPUs: 0-1.

\- Usable RAM: approximately 3.3 GiB.

\- Virtual disk: approximately 20 GB.

\- Reported available disk space at initial inspection: approximately 8.7 GB.

\- cgroup version: v2.



Installed and available:



\- Python 3.14.4.

\- bpftrace 0.25.0.

\- bpftool 7.7.0.

\- libbpf 1.7.

\- perf 7.0.14.

\- Git and pip are ready.



Kernel capabilities confirmed:



\- CONFIG\_BPF.

\- CONFIG\_BPF\_SYSCALL.

\- CONFIG\_BPF\_EVENTS.

\- CONFIG\_DEBUG\_INFO\_BTF.

\- CONFIG\_TRACEPOINTS.

\- CONFIG\_SCHEDSTATS.

\- CONFIG\_FTRACE.

\- BTF available.



Scheduler tracepoints confirmed:



\- sched\_wakeup.

\- sched\_switch.

\- sched\_migrate\_task.

\- sched\_process\_exit.

\- sched\_stat\_wait.



The bpftrace smoke test successfully attached to sched\_wakeup and collected scheduler events.



The following settings were observed:



\- kernel.unprivileged\_bpf\_disabled = 2.

\- kernel.perf\_event\_paranoid = 4.



Therefore, the tracing process should normally run through sudo. Do not run the entire project, Python runner, Codex, or repository as root.



cgroup details:



\- cgroup v2.

\- Available controllers include cpu, cpuset, memory, io, pids, and others.

\- cpu, memory, and pids subtree controllers were enabled.

\- CPU weight was reported as 100 at the checked level.

\- CPU quota was reported as max 100000 at the checked level.



Treat these as environment observations, not hardcoded assumptions.



\## Resource limitations



The VM has only two virtual CPUs and approximately 3.3 GiB of usable RAM.



Consequently:



\- Keep workload generators lightweight.

\- Run experiments sequentially.

\- Avoid spawning unnecessary processes.

\- Keep tracing output manageable.

\- Do not execute several experiments concurrently.

\- Avoid excessive logging or memory accumulation.

\- Record the actual VM configuration in every experiment manifest.



Do not change kernel configuration, sysctl settings, or host scheduler settings automatically.



\---



\# 4. TECHNICAL STACK



Use:



\### Primary languages



\- Python 3.

\- bpftrace.



\### Python packages



\- NumPy.

\- Pandas.

\- Matplotlib.

\- pytest.



Use the Python standard library for subprocess handling, configuration, JSON, CSV, timing, logging, and process management wherever practical.



Keep dependencies minimal.



Check that selected package versions support Python 3.14.4. If a dependency does not support this environment, explain the issue and suggest the least disruptive alternative. Do not replace the system Python installation.



\### Other tools



\- Git for version control.

\- Linux scheduler tracepoints.

\- Linux cgroup v2 where useful.

\- LaTeX/IEEE conference template for the paper.



Use JSON configuration files initially. A database is not required.



\---



\# 5. PROJECT ARCHITECTURE



Build the project using a modular architecture.



The intended execution flow is:



1\. Experiment configuration.

2\. Experiment runner.

3\. Interactive and batch workload generators.

4\. Linux scheduler.

5\. eBPF/bpftrace telemetry collector.

6\. Raw event storage.

7\. Python event parser.

8\. Runnable-wait and CPU-service reconstruction.

9\. Metrics and fairness calculations.

10\. Policy comparison.

11\. Graph generation.

12\. Research-paper results and reproduction documentation.



The system must preserve raw experimental data separately from processed analysis output.



\## Suggested repository structure



Create this structure, adjusting it only when technically justified:



cpu-scheduling-fairness/



&#x20;   README.md

&#x20;   AGENTS.md

&#x20;   pyproject.toml

&#x20;   requirements.txt

&#x20;   .gitignore



&#x20;   configs/

&#x20;       workloads.json

&#x20;       experiment\_matrix.json

&#x20;       policies.json



&#x20;   src/

&#x20;       cpu\_fairness/

&#x20;           \_\_init\_\_.py

&#x20;           cli.py

&#x20;           config.py

&#x20;           system\_info.py

&#x20;           experiment\_runner.py



&#x20;           workloads/

&#x20;               \_\_init\_\_.py

&#x20;               interactive.py

&#x20;               batch\_worker.py



&#x20;           telemetry/

&#x20;               \_\_init\_\_.py

&#x20;               scheduler.bt

&#x20;               collector.py

&#x20;               parser.py



&#x20;           policies/

&#x20;               \_\_init\_\_.py

&#x20;               baseline.py

&#x20;               fixed\_nice.py

&#x20;               wait\_aware\_simulator.py



&#x20;           analysis/

&#x20;               \_\_init\_\_.py

&#x20;               wait\_episodes.py

&#x20;               cpu\_accounting.py

&#x20;               metrics.py

&#x20;               fairness.py

&#x20;               aggregation.py

&#x20;               plots.py



&#x20;   scripts/

&#x20;       preflight.sh

&#x20;       smoke\_test.sh

&#x20;       run\_quick\_experiment.sh

&#x20;       run\_full\_experiment.sh

&#x20;       generate\_analysis.sh



&#x20;   tests/

&#x20;       fixtures/

&#x20;       test\_config.py

&#x20;       test\_trace\_parser.py

&#x20;       test\_wait\_episodes.py

&#x20;       test\_cpu\_accounting.py

&#x20;       test\_metrics.py

&#x20;       test\_fairness.py

&#x20;       test\_policies.py

&#x20;       test\_experiment\_runner.py



&#x20;   docs/

&#x20;       architecture.md

&#x20;       methodology.md

&#x20;       metric\_definitions.md

&#x20;       development\_guide.md

&#x20;       reproduction\_guide.md

&#x20;       limitations.md



&#x20;   results/

&#x20;       raw/

&#x20;           .gitkeep

&#x20;       processed/

&#x20;           .gitkeep

&#x20;       figures/

&#x20;           .gitkeep



&#x20;   paper/

&#x20;       main.tex

&#x20;       references.bib

&#x20;       figures/

&#x20;       README.md



&#x20;   submission/

&#x20;       .gitkeep



Use proper Python package organisation and pathlib for file paths.



Do not create files merely to fill the structure. Every module should have a meaningful responsibility.



\---



\# 6. WORKLOAD GENERATION



We require two types of CPU workloads.



\## 6.1 Interactive workload



Implement an interactive-style workload generator.



Characteristics:



\- Periodic request arrivals.

\- Short CPU-intensive work bursts.

\- Configurable request arrival interval.

\- Configurable CPU burst size.

\- Configurable total experiment duration.

\- Deterministic workload generation where possible.

\- Configurable random seed if randomisation is used.



Each request should be recorded in a JSONL file with:



\- Request ID.

\- Intended release timestamp.

\- Actual execution-start timestamp.

\- Completion timestamp.

\- Workload configuration.

\- Burst work performed.



Use time.monotonic\_ns() or an appropriate monotonic clock for application timestamps.



The intended release time must be recorded before the process sleeps until the next scheduled request. This makes the response-latency measurement include scheduling delay.



Calculate:



Response latency = completion timestamp - intended release timestamp.



Also record observed execution-start time to help distinguish delayed dispatch from CPU service time.



Avoid excessive disk writes during the workload. Buffer or write request data efficiently without losing records.



\## 6.2 Batch workload



Implement a CPU-intensive batch worker.



Characteristics:



\- Sustained CPU computation.

\- Configurable computation-unit size.

\- Configurable execution duration.

\- Multiple independent worker processes.

\- No unnecessary sleeping.

\- Deterministic work units.

\- A completion counter or equivalent throughput measurement.



Each worker should report:



\- Worker ID.

\- PID.

\- Nice value.

\- Number of completed work units.

\- Execution duration.

\- Configuration.

\- Completion status.



Make the workload CPU-bound, not disk-bound or network-bound.



Avoid using threads when separate processes are more appropriate for our scheduler experiments.



The experiment runner should know the PID of each workload process.



The workload should be easy to reproduce with the same parameters.



\---



\# 7. eBPF SCHEDULER TELEMETRY



This is one of the most important parts of the project.



Use bpftrace as our primary collector.



Do not introduce BCC or another tracing framework unless there is a demonstrated compatibility issue.



\## 7.1 Required events



Collect the following where available:



1\. sched\_wakeup.

2\. sched\_switch.

3\. sched\_migrate\_task.

4\. sched\_process\_exit.

5\. sched\_stat\_wait.



Check whether sched\_wakeup\_new is available and include it where practical to observe newly runnable tasks.



The implementation must inspect actual tracepoint availability and fields instead of assuming all Linux kernels expose exactly the same format.



Our confirmed primary event fields include:



\### sched\_wakeup



\- pid.

\- prio.

\- target\_cpu.



\### sched\_switch



\- prev\_pid.

\- prev\_prio.

\- prev\_state.

\- next\_pid.

\- next\_prio.



\### sched\_migrate\_task



\- pid.

\- orig\_cpu.

\- dest\_cpu.



\### sched\_process\_exit



\- pid.

\- group\_dead.



\### sched\_stat\_wait



\- pid.

\- delay.



Store timestamps with nanosecond precision using bpftrace's nsecs or an equivalently appropriate monotonic kernel clock.



Use numeric process identifiers as task identities. Do not rely on process names because names are short and non-unique.



\## 7.2 Trace output format



Produce raw, machine-readable event records.



Prefer a consistent tab-separated output format or another format that can reliably be parsed by Python.



Every record should contain:



\- Timestamp.

\- Event type.

\- PID.

\- Previous PID if relevant.

\- Next PID if relevant.

\- Previous task state if relevant.

\- Priority if available.

\- CPU information if available.

\- Migration source/destination if relevant.

\- Scheduler-reported wait delay if relevant.



Use explicit missing-value markers.



Do not depend on human-readable aggregate map output as the primary experimental dataset.



Save:



\- Raw trace output.

\- bpftrace standard error.

\- Collector start/stop times.

\- Collector exit status.

\- Warnings and possible event-loss information.



Do not silently discard malformed records.



\## 7.3 Correct runnable-wait reconstruction



This is a critical methodological requirement.



Do not calculate runnable delay using only sched\_wakeup-to-sched\_switch pairs.



A task can also be preempted while remaining runnable, in which case its waiting period begins when it is switched out and remains eligible for execution.



Reconstruct runnable-wait episodes from the raw event stream.



Use the following conceptual method:



Maintain per-task state:



\- ready\_since timestamp.

\- last\_scheduled\_in timestamp.

\- cumulative CPU service time.

\- completed wait episodes.

\- migration count.

\- relevant event counters.



When a task becomes runnable through sched\_wakeup, or sched\_wakeup\_new when supported:



\- Record the runnable timestamp.

\- Avoid accidentally replacing an earlier unfinished ready timestamp.

\- Record unexpected duplicate events for validation.



When processing sched\_switch:



1\. Examine the next\_pid.

2\. If the task has a pending runnable timestamp, calculate its wait:

&#x20;
&#x20;  wait\_ns = switch\_timestamp\_ns - ready\_since\_ns



3\. Record the wait episode.

4\. Clear the pending runnable timestamp.

5\. Record the time at which next\_pid begins executing.

6\. Examine prev\_pid.

7\. If prev\_state indicates TASK\_RUNNING/runnable (normally numeric state 0), record the switch-out timestamp as the beginning of its next runnable-wait episode.

8\. When that task is scheduled again, close the pending episode.

9\. Avoid accidentally creating or closing duplicate episodes for the same task.



Use process-exit events to clear unfinished per-task state where appropriate.



Record unfinished wait intervals at the end of tracing as censored/incomplete observations. Do not silently treat them as completed wait episodes.



Validate ordering by sorting raw records by timestamp during analysis, while preserving the original raw trace.



Document possible concurrency, clock, event-loss, and event-ordering limitations.



Use sched\_stat\_wait as an independent comparison or validation source where meaningful. Do not simply add its delay values to reconstructed wait episodes, since they are not necessarily equivalent observations.



\## 7.4 CPU execution-time reconstruction



Use sched\_switch timestamps to estimate per-task CPU service time.



Conceptually:



\- Record a task's scheduled-in timestamp.

\- When it is switched out, calculate the elapsed scheduled execution interval.

\- Accumulate service time per PID.

\- Account for worker termination and incomplete intervals.

\- Handle migrations carefully.

\- Ignore or explicitly mark incomplete intervals when the tracing session begins or ends midway through a task's execution.



Record:



\- Per-task CPU service time.

\- Per-class CPU service time.

\- Scheduled-in counts.

\- Context-switch counts.

\- Migration counts.



Describe the exact accounting method in the documentation.



\---



\# 8. EXPERIMENT RUNNER



Build a reliable experiment orchestration system.



It should:



1\. Load an experiment configuration.

2\. Record system information.

3\. Create a unique run ID.

4\. Create a dedicated output directory.

5\. Start the bpftrace collector.

6\. Confirm that tracing starts successfully.

7\. Launch interactive and batch processes.

8\. Record their PIDs and workload roles.

9\. Run the workload for the configured duration.

10\. Stop the workload cleanly.

11\. Stop the collector and preserve its output.

12\. Record exit statuses and errors.

13\. Save all run metadata.

14\. Validate that expected output exists.

15\. Mark incomplete or failed runs instead of presenting them as successful.



The Python experiment runner must not run as root.



Only the tracer should be launched with sudo when necessary.



Where practical:



\- Request sudo authentication once.

\- Use non-interactive privileged execution after authentication.

\- Fail clearly when privileges are unavailable.

\- Never suppress permission errors.



Do not modify global scheduler parameters.



Do not modify host-level resource controls.



Do not run experiments concurrently on this small VM.



Ensure all spawned child processes are stopped cleanly if a run is interrupted.



\---



\# 9. EXPERIMENT DESIGN



Build both a quick test mode and a full experiment mode.



\## Quick mode



Used to verify that everything works.



Suggested settings:



\- One repetition.

\- Short duration.

\- One workload combination.

\- Default scheduler configuration.

\- A small number of batch workers.



It must generate real trace data, workload logs, and a basic analysis report.



\## Full mode



The assignment recommends a repeatable experiment matrix.



Target:



\- 3 contention levels.

\- 3 interactive workload profiles/mixes.

\- 5 repetitions per combination.

\- 2 measured scheduling configurations: baseline and fixed nice.



This gives 90 measured experimental runs.



A wait-aware simulator can subsequently process the collected traces and must remain separately labelled.



Use adjustable parameters rather than hardcoding the entire experiment design.



The initial contention levels can use batch-worker counts such as:



\- 1 worker.

\- 2 workers.

\- 4 workers.



These should be interpreted in the context of our two-vCPU guest.



Create three configurable interactive workload profiles with different request frequencies and CPU burst sizes.



Pilot the workload first and check that the bursts, response times, and trace volume are sensible.



Run a small pilot before starting the full matrix.



The experiment runner should be able to resume or skip completed runs without overwriting raw data.



Record seeds, configuration values, start/end times, and experiment IDs.



\---



\# 10. MEASUREMENTS AND METRICS



Implement a clear metrics module.



For interactive workloads:



\- Response latency p50.

\- Response latency p95.

\- Response latency p99.

\- Average response latency.

\- Maximum response latency.

\- Average runnable wait.

\- Runnable-wait p50/p95/p99.

\- Maximum runnable wait.

\- Number of long-wait episodes.

\- Number of requests completed.



For batch workloads:



\- Total completed work units.

\- Batch throughput (work units per second).

\- Per-worker CPU service time.

\- Per-worker CPU share.

\- Variation in CPU allocation among comparable batch workers.



For the complete experiment:



\- Total CPU service time.

\- Per-task service distribution.

\- Context switches.

\- CPU migrations.

\- CPU utilisation where measured reliably.

\- Instrumentation overhead.

\- Dropped or incomplete trace-event warnings.



\## Fairness metrics



Use the project-defined capacity-normalized Delta (Δ) and directional partitioned ΔB→I metrics over scheduler-clock micro-windows, as specified in `docs/metric_definitions.md`.



For each active target task in a window, calculate runnable demand R_i = E_i + W_i, fair capacity C_i = M × τ × w_i / Σw_j, entitlement Ent_i = min(R_i, C_i), and normalized service x_i = min(1, E_i / Ent_i). Calculate deficits d_i = max(x_j) - x_i, global Δ = mean(d_i), and class means m_I and m_B. Report ΔB→I = max(0, m_I - m_B) and ΔI→B = max(0, m_B - m_I).



Use only verified target-task identities, CPU affinity, scheduler weights, and complete micro-windows. Confirm that no restrictive cgroup CPU quota changes the usable capacity. Omit or mark a directional result unavailable when both workload classes are not represented. Do not trigger a scheduling policy from this measurement stage.



Document the active-demand threshold, window boundaries, weight source, handling of incomplete or lost intervals, and any selected SLO-derived threshold ε. Keep measured fairness analysis separate from the wait-aware policy simulator.



Do not invent ideal service shares without justification.



\## Statistical analysis



For repeated experiments:



\- Report sample counts.

\- Report medians and appropriate means.

\- Calculate confidence intervals, preferably using bootstrap intervals for aggregated metrics.

\- Show variation between runs.

\- Avoid presenting unstable p99 measurements without reporting sample sizes.

\- Use paired comparisons where runs have matching workload settings.



Do not claim that a difference is statistically significant without suitable analysis.



\---



\# 11. POLICY SIMULATOR



Implement a separate wait-aware policy simulator.



It should:



\- Read measured scheduler data.

\- Identify tasks with long runnable waits.

\- Apply a configurable wait threshold.

\- Generate bounded boost requests.

\- Use aging.

\- Limit the maximum boost.

\- Enforce cooldown or equivalent anti-oscillation behaviour.

\- Produce a policy-decision log.

\- Include tests for boundedness and starvation safeguards.



The simulator should be independently testable with synthetic input fixtures.



It must clearly distinguish:



\- Measured scheduler observations.

\- Simulated policy decisions.

\- Hypothetical outcomes.



Do not generate fictional post-mitigation performance data.



If a real dynamic controller is attempted later, it must be a separately documented optional extension, and its results must come from actual experiments.



\---



\# 12. DATA STORAGE AND REPRODUCIBILITY



For every experiment, store a manifest containing:



\- Run ID.

\- Timestamp.

\- Git commit hash, if available.

\- Kernel version.

\- Ubuntu version.

\- CPU model.

\- Number of vCPUs.

\- Memory allocation.

\- Virtualisation platform.

\- bpftrace version.

\- Python version.

\- Relevant tool versions.

\- cgroup version and available controllers.

\- Workload parameters.

\- Policy configuration.

\- Random seed.

\- Process IDs.

\- Nice values.

\- Collector start/end times.

\- Event counts.

\- Warnings.

\- Exit statuses.



Store raw and processed output separately.



Do not overwrite raw data.



Do not confuse sample test fixtures with actual measured results.



Add appropriate results directories to .gitignore where large raw files should not be committed.



Preserve a small, clearly identified real sample dataset only after successfully collecting it from our experimental VM.



All figures in the final paper must be generated from actual experiment data.



\---



\# 13. AUTOMATED ANALYSIS AND GRAPHS



Use Pandas, NumPy, and Matplotlib.



Generate at least these graphs when suitable data exists:



1\. Interactive response latency comparison between scheduling configurations.

2\. p95/p99 interactive latency under increasing batch contention.

3\. Runnable-wait distribution comparison.

4\. Batch throughput comparison.

5\. Per-worker CPU service-time distribution.

6\. Global Delta and directional ΔB→I / ΔI→B values across scheduler windows.

7\. Trade-off graph showing interactive latency against batch throughput.

8\. Scheduler waiting-time distribution or CDF.



Use clear axis labels, units, legends, and explanatory captions.



Save plots as PNG and, where practical, PDF for the paper.



Do not generate attractive but misleading charts.



Clearly mark simulated results if any simulator outputs are visualised.



\---



\# 14. TESTING AND VALIDATION



Implement unit tests for all important modules.



At minimum, test:



\- Configuration parsing.

\- Trace parsing.

\- Missing and malformed event handling.

\- Scheduler wait reconstruction.

\- Preemption-based runnable-wait handling.

\- Duplicate wakeup handling.

\- Incomplete intervals.

\- CPU-service accounting.

\- Delta and directional fairness calculations.

\- Percentile calculation.

\- Policy bounds and aging.

\- Experiment failure handling.

\- Data-manifest creation.



Create small synthetic trace fixtures with known expected answers.



For example, create a test where:



\- Task 101 wakes at timestamp 100.

\- Task 101 is scheduled at timestamp 350.



The reconstructed runnable wait should be 250 nanoseconds.



Also test a preemption case:



\- Task 101 is switched out in TASK\_RUNNING state at timestamp 500.

\- Task 101 is scheduled again at timestamp 800.



The reconstructed runnable wait should be 300 nanoseconds.



Add tests for incomplete and malformed data.



Run portable unit tests on the development machine, including Windows if that is where Codex runs.



Linux-only integration tests must detect the platform and skip cleanly when bpftrace or the required tracepoints are unavailable.



Do not pretend a Windows unit test proves that Linux eBPF tracing works.



The final validation must happen inside the actual Ubuntu guest.



\---



\# 15. SAFETY AND SYSTEM INTEGRITY



This project is intended for an authorised disposable experimental VM.



Never run experiments on production systems.



Never run Codex or the complete Python project as root.



Never change the host's kernel settings or scheduler policy automatically.



Do not use broad destructive shell commands.



Do not delete existing experiment results.



Do not silently overwrite user files.



Ask before performing privileged operations that change system configuration.



The bpftrace collector may require sudo, but the rest of the application must remain a normal user process.



Provide clear instructions for every privileged command.



\---



\# 16. RESEARCH PAPER



Prepare an IEEE conference-style LaTeX paper with a maximum target of six pages.



Required sections:



1\. Problem Definition.

2\. Objectives.

3\. Literature Survey.

4\. Methodology Used.

5\. Experimental Results.

6\. Conclusion.

7\. References.



Use an appropriate IEEE conference template.



The paper should explain:



\- The problem of CPU scheduling unfairness.

\- Why interactive and batch workloads are being compared.

\- The fairness definition used.

\- The measurement methodology.

\- eBPF tracepoint selection.

\- Runnable-wait reconstruction.

\- Workload design.

\- Scheduling configurations.

\- Experimental environment.

\- Metrics and statistical analysis.

\- Actual experimental results.

\- Limitations.

\- Possible future improvements.



\## Literature survey requirements



Find at least five directly relevant, credible academic research sources.



Prefer peer-reviewed conference or journal papers.



Verify titles, authors, publication venue, year, and DOI or another stable publication identifier.



Do not invent references, DOI numbers, publication venues, or research findings.



Use primary academic sources wherever possible.



Blogs and documentation can support technical implementation descriptions but must not be falsely presented as peer-reviewed research.



If a reference cannot be verified, mark it for human verification rather than fabricating its details.



Use BibTeX.



Follow the IEEE citation style.



\## Results integrity



Do not fabricate:



\- Experimental measurements.

\- Charts.

\- Performance improvements.

\- Statistical significance.

\- Research citations.

\- Conclusions.



Before actual experiments have been performed, use clearly marked placeholders in the paper.



Once real measurements exist, populate the results section from the actual analysis outputs.



Report negative or inconclusive results honestly.



Do not claim novelty without supporting evidence.



\---



\# 17. REQUIRED FINAL DELIVERABLES



Prepare these four deliverables.



\### Deliverable 1 — IEEE\_Report.pdf



The completed six-page IEEE-style research paper.



\### Deliverable 2 — IEEE\_LaTeX\_Source.zip



Include:



\- main.tex.

\- references.bib.

\- Figure files.

\- Any required IEEE template files that we are permitted to redistribute.

\- Instructions to compile.



\### Deliverable 3 — Project\_Source\_Code.zip



Include:



\- Python source code.

\- bpftrace scripts.

\- Workload generators.

\- Policy implementations.

\- Analysis scripts.

\- Test files.

\- Configurations.

\- README.

\- Dependency information.

\- Reproduction instructions.

\- Appropriate sample results, if collected.



Exclude:



\- .venv.

\- Python cache files.

\- Unnecessary editor files.

\- Huge temporary outputs.

\- Credentials or personal data.



\### Deliverable 4 — Reproduction\_Guide.pdf



Explain:



\- Project architecture.

\- Purpose of each module.

\- Dependencies.

\- Installation procedure.

\- Required Ubuntu/kernel features.

\- bpftrace configuration.

\- Execution commands.

\- Configuration options.

\- Workload generation.

\- Experiment execution.

\- Data storage.

\- Analysis and graph generation.

\- Policy implementation.

\- How to reproduce the reported results.

\- Expected outputs.

\- Troubleshooting.

\- Limitations.



\---



\# 18. FOUR-MEMBER TEAM ORGANISATION



Design clear module boundaries for four team members.



Suggested allocation:



\*\*Member 1 — Workload and Experiment Management\*\*



Responsible for:



\- Interactive workload generator.

\- Batch workload generator.

\- Experiment runner.

\- Workload configurations.

\- Run metadata.



\*\*Member 2 — eBPF and Telemetry\*\*



Responsible for:



\- bpftrace scheduler collector.

\- Event schema.

\- Event parser.

\- Runnable-wait reconstruction.

\- CPU-service accounting.

\- Trace validation.



\*\*Member 3 — Metrics and Analysis\*\*



Responsible for:



\- Latency analysis.

\- Throughput.

\- CPU share.

\- Delta and directional fairness.

\- Statistical analysis.

\- Graph generation.



\*\*Member 4 — Policies, Reproducibility and Paper\*\*



Responsible for:



\- Fixed nice policy integration.

\- Wait-aware policy simulator.

\- Policy tests.

\- Literature survey.

\- Reproduction guide.

\- IEEE paper integration.



Establish shared interfaces before the modules are developed independently.



Create a CONTRIBUTING.md or equivalent explaining:



\- Module ownership.

\- Expected input/output formats.

\- File naming.

\- Configuration conventions.

\- Branch and integration workflow.

\- How to run tests.



Do not let different members implement conflicting event schemas or metric definitions.



\---



\# 19. REQUIRED COMMAND-LINE INTERFACE



Provide a simple CLI.



Use a consistent interface similar to:



&#x20;   python -m cpu\_fairness.cli preflight



&#x20;   python -m cpu\_fairness.cli smoke



&#x20;   python -m cpu\_fairness.cli run --config configs/...



&#x20;   python -m cpu\_fairness.cli run-matrix --mode quick



&#x20;   python -m cpu\_fairness.cli run-matrix --mode full



&#x20;   python -m cpu\_fairness.cli analyse --run-dir ...



&#x20;   python -m cpu\_fairness.cli package



These are desired command concepts, not permission to create an unnecessarily complicated CLI.



Choose sensible arguments and document the exact final commands.



The preflight command should check:



\- Linux platform.

\- Kernel information.

\- Python version.

\- bpftrace availability.

\- Required tracepoints.

\- BTF availability.

\- Trace filesystem availability.

\- cgroup v2.

\- Available CPUs and memory.

\- Writable output directories.

\- Required Python packages.



The smoke test should verify:



\- Collector startup.

\- Scheduler event collection.

\- Workload execution.

\- PID identification.

\- Raw data creation.

\- Parsing.

\- At least one valid scheduler wait observation.

\- Basic analysis output.



Fail with useful error messages instead of producing empty or fake result files.



\---



\# 20. REQUIRED DEVELOPMENT PROCESS



Do not attempt to generate a huge amount of untested code in one pass.



Work in the following phases, but continue through the phases autonomously unless a genuine blocker requires human input.



\## Phase 0 — Repository inspection and architecture



First:



\- Inspect the repository.

\- Read existing files.

\- Check the development operating system.

\- Identify whether the terminal is Windows or Linux.

\- Create AGENTS.md with the project rules.

\- Establish module boundaries and data contracts.



Do not overwrite existing work.



\## Phase 1 — Project foundation



Create:



\- Project structure.

\- Python package.

\- Dependency files.

\- Configuration files.

\- CLI foundation.

\- System-information collector.

\- Unit-test foundation.

\- README.



Verify portable tests.



\## Phase 2 — Workload implementation



Build and test the interactive and batch workload generators.



Verify that they produce valid structured logs and expose their PIDs.



\## Phase 3 — eBPF telemetry



Implement:



\- bpftrace script.

\- Linux preflight.

\- Collector management.

\- Raw event schema.

\- Trace parser.

\- Error and event-loss reporting.



Run portable parser tests.



Do not claim the Linux collector is fully validated until it has been tested inside the Ubuntu guest.



\## Phase 4 — Scheduler analysis



Implement:



\- Runnable-wait reconstruction.

\- Preemption-based waiting.

\- CPU-service accounting.

\- Migration and context-switch metrics.

\- Synthetic trace tests.



\## Phase 5 — Experiment and policy implementation



Implement:



\- Default scheduler configuration.

\- Fixed nice configuration.

\- Wait-aware policy simulator.

\- Experiment runner.

\- Quick experiment mode.

\- Full experiment matrix.

\- Run manifests and raw data preservation.



\## Phase 6 — Metrics and visualisation



Implement:



\- Latency metrics.

\- Throughput.

\- CPU service shares.

\- Fairness.

\- Statistical analysis.

\- Trade-off plots.

\- Automated analysis output.



\## Phase 7 — Documentation and paper



Prepare:



\- Methodology document.

\- Architecture documentation.

\- Metric definitions.

\- Reproduction guide.

\- IEEE paper structure.

\- Verified literature references.

\- Submission packaging scripts.



Do not fill result placeholders using fictional data.



\## Phase 8 — Final integration



Run the available portable tests.



Prepare a Linux integration test checklist.



Give us exact commands to transfer or pull the repository into the Ubuntu guest and run it there.



After actual Linux test results are available, fix any problems revealed by those tests.



Do not mark Linux-only features as passed merely because code has been generated.



\---



\# 21. HOW YOU SHOULD COMMUNICATE WITH US



We are beginners.



For each phase:



1\. Briefly explain the purpose of the module.

2\. Explain the important design decisions.

3\. Implement the module.

4\. Run tests that are safe and available in the current environment.

5\. Report exactly which tests passed and failed.

6\. Explain how to test Linux-only functionality in the Ubuntu guest.

7\. Document remaining limitations.



Use beginner-friendly explanations, but do not oversimplify important OS concepts.



Do not ask us to make decisions that can be handled through a reasonable, configurable default.



Do not make unsupported assumptions.



Do not claim files, experiments, tests, or results exist unless they actually do.



Do not claim an implementation is complete until it has been tested to the degree possible in the current environment.



If there is a technical blocker, explain it and propose the simplest defensible solution.



If an optional extension threatens the minimum working project, prioritise the core deliverables.



Do not spend excessive time optimising code that already meets the requirements.



\---



\# 22. FIRST ACTION



Start now.



First inspect the repository and the environment available to Codex.



Then create a concise architecture and implementation plan in docs/architecture.md.



After that, start implementing the project foundation and proceed through the phases above.



Do not stop after merely explaining the architecture.



Our primary goal is a working, tested, reproducible Operating Systems research project that can be completed within our seven-day team sprint.



\*\*Priorities, in order:\*\*



1\. Correct scheduler measurement.

2\. Working eBPF telemetry.

3\. Repeatable workload generation.

4\. Valid experiment results.

5\. Fairness and performance analysis.

6\. Reproducibility.

7\. Research-paper quality.

8\. Optional improvements.



Accuracy, reproducibility, and honest reporting are more important than unnecessary complexity.
