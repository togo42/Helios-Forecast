#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
if [[ "$#" -ne 2 || "$1" != --ref ]]; then
    echo "Usage: bash scripts/install_review_hook.sh --ref FROZEN_DELIVERY_BASE" >&2
    exit 2
fi
base="$(git rev-parse --verify "$2^{commit}")"
existing="$(git config --get core.hooksPath || true)"
if [[ -n "$existing" && "$existing" != .githooks ]]; then
    echo "Existing core.hooksPath must be reconciled explicitly: $existing" >&2
    exit 1
fi
native="$(git rev-parse --git-path hooks/pre-push)"
if [[ -e "$native" && "$existing" != .githooks ]]; then
    echo 'Existing native pre-push hook must be reconciled explicitly' >&2
    exit 1
fi
git config --local aiReview.deliveryBase "$base"
git config --local core.hooksPath .githooks
echo 'Local pre-push review gate enabled; GitHub/provider enforcement is separate.'
