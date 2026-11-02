#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "the scheduler smoke experiment is Linux-only; run it inside the Ubuntu guest" >&2
    exit 2
fi
if [[ "$(id -u)" -eq 0 ]]; then
    echo "do not run the project runner as root; only its bpftrace child uses sudo" >&2
    exit 2
fi

exec python3 -m cpu_fairness.cli smoke --config "${1:-configs/quick.json}" --output-root "${2:-results}"
