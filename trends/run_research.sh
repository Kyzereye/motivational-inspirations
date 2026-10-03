#!/bin/bash
# Trend & Content Research Agent — runs trends/TASK.md through the Claude Code CLI
# (headless mode), using the existing Claude Code subscription rather than a
# separate metered API key.
#
# Usage:
#   ./trends/run_research.sh              # interactive: you approve each tool call
#   ./trends/run_research.sh --unattended # no prompts — for cron, once trusted
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

ALLOWED_TOOLS="Read,Grep,Bash,Write,WebSearch"
MODEL="claude-opus-5"

EXTRA_FLAGS=()
if [[ "${1:-}" == "--unattended" ]]; then
  EXTRA_FLAGS+=(--permission-mode dontAsk --permission-prompts none)
fi

claude -p "$(cat trends/TASK.md)" \
  --model "$MODEL" \
  --allowedTools "$ALLOWED_TOOLS" \
  --output-format text \
  "${EXTRA_FLAGS[@]}"
