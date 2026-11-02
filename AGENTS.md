# Project-wide working rules

- Treat `Project_Spec.md` as authoritative. Keep the project small enough for a seven-day beginner team sprint; prioritize a real baseline end-to-end experiment.
- Do not implement `sched_ext`, a kernel module, a live dynamic scheduler controller, a dashboard, a database, or other excluded scope. The wait-aware policy is a simulator only.
- Develop and run portable Python logic on Windows if useful. Real scheduler experiments, bpftrace collection, Linux tracepoint checks, nice-policy runs, and final integration validation belong in the specified Ubuntu KVM guest. Never claim Windows validates Linux eBPF.
- Keep the Python runner and workloads unprivileged. Elevate only the tracer command when necessary. Never change kernel/sysctl/host scheduler settings automatically or run experiments on production systems.
- Preserve user data and raw results. Never overwrite or delete existing result files; assign each run a unique output directory and fail if it already exists. Do not treat the existing root CSV files as validated experiment data.
- Preserve raw traces separately from parsed/processed output. Record environment, configuration, PIDs, exit statuses, warnings, and incomplete/lost-data indicators. Never fabricate measurements, plots, citations, or policy outcomes.
- Agree on event schema, monotonic timestamp units, PID identity, workload log schema, and metric definitions before parallel module work. Use numeric task IDs; document PID reuse/thread-vs-process limitations.
- Reconstruct runnable waits after wakeup and runnable preemption; handle duplicates, exits, unfinished intervals, ordering, and malformed events explicitly. Keep scheduler-reported `sched_stat_wait` separate as a validation source.
- Calculate Jain fairness only over comparable equal-demand workers. Keep simulated decisions distinct from measured results. Label sample fixtures as synthetic.
- Keep workloads deterministic/configurable and lightweight. Run experiments sequentially on the two-vCPU guest; pilot before any larger matrix.
- Use Python standard library where practical and verify third-party dependency support on the target Python before pinning/installing. Do not replace system Python.
- Make changes in small reviewable steps. Do not claim a check passed unless it was actually run; distinguish portable checks from Ubuntu guest integration checks.
