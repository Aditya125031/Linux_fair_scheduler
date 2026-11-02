#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "preflight is Linux-only; run it inside the Ubuntu guest" >&2
    exit 2
fi

exec python3 -m cpu_fairness.cli preflight "$@"
