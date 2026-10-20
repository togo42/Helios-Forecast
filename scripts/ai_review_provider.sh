#!/usr/bin/env bash
# Helios facade around HA-Config transport (ESS-derived); no provider fallback.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/ai_review_transport.sh"
TARGET_MODEL='Gemini 3.8 Flash (High)'
REVIEWER=gemini
MODE=helios
prompt_file="$1/prompt.md"
response_file="$1/response.json"
error_file="$1/provider.stderr"
chunk_dir="$1/transcript"
mkdir -p "$chunk_dir"
agy_log_file="$chunk_dir/agy_cli.log"
# Always use sequential acknowledged chunks and a separate final turn.
# No legacy/provider/model fallback; unsupported stream protocol fails closed.
validate_positive_integer AI_REVIEW_CHUNK_BYTES "$CHUNK_BYTES"
if [[ "$CHUNK_BYTES" -gt 100000 ]]; then
    echo "AI_REVIEW_CHUNK_BYTES exceeds the 100000-byte cap" >&2
    exit 2
fi
CHUNKING_POLICY=on
agy_stream_supported=yes
review_transport_run
