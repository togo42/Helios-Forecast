#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mode=full
args=()
for arg in "$@"; do
    case "$arg" in
        --full) mode=full ;;
        --meta) mode=meta ;;
        *) args+=("$arg") ;;
    esac
done
exec python3 "$SCRIPT_DIR/ai_review.py" run --mode "$mode" "${args[@]}"
