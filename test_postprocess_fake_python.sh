#!/usr/bin/env bash
# Test-only stand-in for the remote Python interpreter.  It records which
# release commands the post-processing gate would invoke, without creating
# result artifacts.
set -euo pipefail

: "${POSTPROCESS_CALL_LOG:?POSTPROCESS_CALL_LOG must be set}"
printf '%s\n' "$(basename "$1")" >> "$POSTPROCESS_CALL_LOG"
case "$(basename "$1")" in
    verify_split_integrity.py)
        [[ "${POSTPROCESS_SUPPRESS_MARKER:-0}" == 1 ]] || echo 'SPLIT_INTEGRITY_COMPLETE'
        ;;
    final_paper_audit.py)
        [[ "${POSTPROCESS_SUPPRESS_MARKER:-0}" == 1 ]] || echo 'FINAL_AUDIT_COMPLETE'
        ;;
esac
