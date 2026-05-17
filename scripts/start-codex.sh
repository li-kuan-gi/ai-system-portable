#!/usr/bin/env sh
set -eu

usage() {
  cat <<'USAGE'
Usage:
  start-codex.sh --workspace <path> [--codex-home <path>] [--codex-bin <path-or-name>] [--dry-run] [--skip-safety-net-check] [--] [codex args...]

Starts Codex from the target workspace root with a dedicated CODEX_HOME.

Defaults:
  --codex-home  $CODEX_HOME, or $HOME/.codex when CODEX_HOME is unset
  --codex-bin   $CODEX_BIN, or codex when CODEX_BIN is unset

The command validates:
  - <WORKSPACE>/AGENTS.md
  - <WORKSPACE>/ai-system/entry.md
  - <CODEX_HOME>/hooks/allow_trusted_script_permission.py
  - <CODEX_HOME>/rules/minimal.rules
  - <CODEX_HOME>/templates/portable-codex-safety-net.config.snippet.toml

It warns when <CODEX_HOME>/config.toml does not appear to reference the
installed hook and workspace. It never edits config.toml.
USAGE
}

workspace=
codex_home=${CODEX_HOME:-}
codex_bin=${CODEX_BIN:-codex}
dry_run=false
skip_safety_net_check=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --workspace)
      workspace=${2:-}
      shift 2
      ;;
    --codex-home)
      codex_home=${2:-}
      shift 2
      ;;
    --codex-bin)
      codex_bin=${2:-}
      shift 2
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    --skip-safety-net-check)
      skip_safety_net_check=true
      shift
      ;;
    --)
      shift
      break
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$workspace" ]; then
  usage >&2
  exit 2
fi

if [ -z "$codex_home" ]; then
  codex_home=$HOME/.codex
fi

abspath() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "$(pwd)" "$1" ;;
  esac
}

warn() {
  echo "warning: $*" >&2
}

fail() {
  echo "ERROR: $*" >&2
  exit 2
}

require_file() {
  if [ ! -f "$1" ]; then
    fail "required file is missing: $1"
  fi
}

require_dir() {
  if [ ! -d "$1" ]; then
    fail "required directory is missing: $1"
  fi
}

resolve_codex_bin() {
  raw=$1
  case "$raw" in
    */*)
      case "$raw" in
        /*) resolved=$raw ;;
        *) resolved=$(abspath "$raw") ;;
      esac
      if [ ! -x "$resolved" ]; then
        fail "codex binary is not executable: $resolved"
      fi
      printf '%s\n' "$resolved"
      ;;
    *)
      resolved=$(command -v "$raw" 2>/dev/null || true)
      if [ -z "$resolved" ]; then
        fail "codex binary not found in PATH: $raw"
      fi
      printf '%s\n' "$resolved"
      ;;
  esac
}

workspace_abs=$(abspath "$workspace")
codex_home_abs=$(abspath "$codex_home")

require_dir "$workspace_abs"
require_file "$workspace_abs/AGENTS.md"
require_file "$workspace_abs/ai-system/entry.md"

if [ "$skip_safety_net_check" != "true" ]; then
  require_dir "$codex_home_abs"
  require_file "$codex_home_abs/hooks/allow_trusted_script_permission.py"
  require_file "$codex_home_abs/rules/minimal.rules"
  require_file "$codex_home_abs/templates/portable-codex-safety-net.config.snippet.toml"
fi

config_file="$codex_home_abs/config.toml"
config_snippet="$codex_home_abs/templates/portable-codex-safety-net.config.resolved.toml"
if [ ! -f "$config_snippet" ]; then
  config_snippet="$codex_home_abs/templates/portable-codex-safety-net.config.snippet.toml"
fi
if [ ! -f "$config_file" ]; then
  warn "$config_file not found; merge $config_snippet before relying on the safety net"
else
  if ! grep -F "allow_trusted_script_permission.py" "$config_file" >/dev/null 2>&1; then
    warn "$config_file does not appear to reference allow_trusted_script_permission.py; merge $config_snippet"
  fi
  if ! grep -F "$workspace_abs" "$config_file" >/dev/null 2>&1; then
    warn "$config_file does not appear to reference workspace: $workspace_abs; merge $config_snippet"
  fi
fi

codex_bin_resolved=$codex_bin
if [ "$dry_run" != "true" ]; then
  codex_bin_resolved=$(resolve_codex_bin "$codex_bin")
fi

if [ "$dry_run" = "true" ]; then
  echo "workspace=$workspace_abs"
  echo "codex_home=$codex_home_abs"
  echo "codex_bin=$codex_bin"
  echo "skip_safety_net_check=$skip_safety_net_check"
  echo "command:"
  echo "  cd $workspace_abs"
  echo "  CODEX_HOME=$codex_home_abs $codex_bin $*"
  exit 0
fi

cd "$workspace_abs"
export CODEX_HOME="$codex_home_abs"
exec "$codex_bin_resolved" "$@"
