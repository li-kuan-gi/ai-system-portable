#!/usr/bin/env sh
set -eu

usage() {
  cat <<'USAGE'
Usage:
  install-portable-system.sh --target-root <path> [--codex-home <path>] [options]

Installs the portable agent system into a target workspace root:
  - AGENTS.md
  - ai-system/

When --codex-home is provided, also installs the Codex safety-net implementation:
  - hooks/allow_trusted_script_permission.py
  - rules/minimal.rules
  - templates/portable-codex-safety-net.config.snippet.toml
  - config.toml when --codex-bin is provided and config.toml is missing or safely replaceable

Options:
  --agent-history-file <path>   Import agent-readable conversation history / handoff markdown
  --agent-settings-file <path>  Import agent-readable settings markdown
  --codex-bin <path|name>       Codex binary path used to materialize the resolved config snippet
  --dry-run                     Print planned changes. Default.
  --apply                       Install files.
  --backup-existing             Back up existing targets before replacing them.

This script does not install auth, secrets, sessions, logs, or cache.
It prints the Codex config snippet path for manual merge.

By default, --apply refuses to overwrite existing target files. With
--backup-existing, existing AGENTS.md / ai-system are moved to:
  <TARGET_ROOT>.ai-system-install-backups/<timestamp>-<pid>/
USAGE
}

target_root=
codex_home=
codex_bin=
agent_history_file=
agent_settings_file=
mode=dry-run
backup_existing=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target-root)
      target_root=${2:-}
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
    --agent-history-file)
      agent_history_file=${2:-}
      shift 2
      ;;
    --agent-settings-file)
      agent_settings_file=${2:-}
      shift 2
      ;;
    --dry-run)
      mode=dry-run
      shift
      ;;
    --apply)
      mode=apply
      shift
      ;;
    --backup-existing)
      backup_existing=true
      shift
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

if [ -z "$target_root" ]; then
  usage >&2
  exit 2
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PACKAGE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

abspath() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "$(pwd)" "$1" ;;
  esac
}

path_exists() {
  [ -e "$1" ] || [ -L "$1" ]
}

config_has_safety_net() {
  file=$1
  [ -f "$file" ] \
    && grep -F "allow_trusted_script_permission.py" "$file" >/dev/null 2>&1 \
    && grep -F "$target_root_abs" "$file" >/dev/null 2>&1
}

target_status() {
  if path_exists "$1"; then
    echo "exists"
  else
    echo "missing"
  fi
}

require_source() {
  if [ ! -e "$1" ]; then
    echo "package source is missing: $1" >&2
    exit 2
  fi
}

require_import_source() {
  if [ ! -f "$1" ]; then
    echo "import source is missing or not a file: $1" >&2
    exit 2
  fi
}

reject_import_inside_target() {
  case "$1" in
    "$target_root_abs"/*)
      echo "import source must be outside target root during install: $1" >&2
      exit 2
      ;;
  esac
}

move_to_backup() {
  src=$1
  dst=$2
  if path_exists "$src"; then
    mkdir -p "$(dirname -- "$dst")"
    mv "$src" "$dst"
    echo "backup: $src -> $dst"
  fi
}

copy_core() {
  mkdir -p "$target_root_abs"
  cp -p "$PACKAGE_ROOT/AGENTS.md" "$target_root_abs/AGENTS.md"
  cp -Rp "$PACKAGE_ROOT/ai-system" "$target_root_abs/ai-system"
  echo "installed portable core into $target_root_abs"
}

import_agent_context() {
  if [ -n "$agent_history_file_abs" ]; then
    cp -p "$agent_history_file_abs" "$target_root_abs/ai-system/knowledge/context/agent-history.md"
    echo "imported agent history: $agent_history_file_abs -> $target_root_abs/ai-system/knowledge/context/agent-history.md"
  fi

  if [ -n "$agent_settings_file_abs" ]; then
    cp -p "$agent_settings_file_abs" "$target_root_abs/ai-system/knowledge/context/agent-settings.md"
    echo "imported agent settings: $agent_settings_file_abs -> $target_root_abs/ai-system/knowledge/context/agent-settings.md"
  fi
}

target_root_abs=$(abspath "$target_root")
codex_home_abs=
if [ -n "$codex_home" ]; then
  codex_home_abs=$(abspath "$codex_home")
fi
agent_history_file_abs=
if [ -n "$agent_history_file" ]; then
  agent_history_file_abs=$(abspath "$agent_history_file")
fi
agent_settings_file_abs=
if [ -n "$agent_settings_file" ]; then
  agent_settings_file_abs=$(abspath "$agent_settings_file")
fi

if [ "$target_root_abs" = "$PACKAGE_ROOT" ]; then
  echo "target root must not be the portable package root" >&2
  exit 2
fi

require_source "$PACKAGE_ROOT/AGENTS.md"
require_source "$PACKAGE_ROOT/ai-system"
if [ -n "$agent_history_file_abs" ]; then
  require_import_source "$agent_history_file_abs"
  reject_import_inside_target "$agent_history_file_abs"
fi
if [ -n "$agent_settings_file_abs" ]; then
  require_import_source "$agent_settings_file_abs"
  reject_import_inside_target "$agent_settings_file_abs"
fi

core_agents_dst="$target_root_abs/AGENTS.md"
core_ai_system_dst="$target_root_abs/ai-system"

echo "package_root=$PACKAGE_ROOT"
echo "target_root=$target_root_abs"
echo "mode=$mode"
echo "backup_existing=$backup_existing"
echo "install core: $PACKAGE_ROOT/AGENTS.md -> $core_agents_dst"
echo "target AGENTS.md status: $(target_status "$core_agents_dst")"
echo "install core: $PACKAGE_ROOT/ai-system -> $core_ai_system_dst"
echo "target ai-system status: $(target_status "$core_ai_system_dst")"

if [ -n "$codex_home_abs" ]; then
  echo "codex_home=$codex_home_abs"
  if [ -n "$codex_bin" ]; then
    echo "codex_bin=$codex_bin"
  else
    echo "codex_bin=(not provided; resolved config snippet not generated)"
  fi
  echo "codex safety-net installer: $PACKAGE_ROOT/implementation-packs/codex-safety-net/scripts/install-safety-net.sh"
  echo "codex config snippet target: $codex_home_abs/templates/portable-codex-safety-net.config.snippet.toml"
  if [ -n "$codex_bin" ]; then
    echo "codex resolved config snippet target: $codex_home_abs/templates/portable-codex-safety-net.config.resolved.toml"
  fi
else
  echo "codex_home=(not provided; skip Codex safety-net install)"
fi
if [ -n "$agent_history_file_abs" ]; then
  echo "agent history import: $agent_history_file_abs -> $target_root_abs/ai-system/knowledge/context/agent-history.md"
else
  echo "agent history import=(not provided; keep initialized template)"
fi
if [ -n "$agent_settings_file_abs" ]; then
  echo "agent settings import: $agent_settings_file_abs -> $target_root_abs/ai-system/knowledge/context/agent-settings.md"
else
  echo "agent settings import=(not provided; keep initialized template)"
fi

if [ "$mode" = "dry-run" ]; then
  exit 0
fi

if [ -n "$codex_home_abs" ] \
  && [ -n "$codex_bin" ] \
  && path_exists "$codex_home_abs/config.toml" \
  && ! config_has_safety_net "$codex_home_abs/config.toml" \
  && [ -s "$codex_home_abs/config.toml" ] \
  && [ "$backup_existing" != "true" ]; then
  echo "target config.toml already exists and does not reference this safety net; rerun with --backup-existing to back it up and replace it, or merge the resolved config snippet manually: $codex_home_abs/config.toml" >&2
  exit 2
fi

if path_exists "$core_agents_dst" || path_exists "$core_ai_system_dst"; then
  if [ "$backup_existing" != "true" ]; then
    echo "target AGENTS.md or ai-system already exists; rerun with --backup-existing to move them aside before install" >&2
    exit 2
  fi
fi

if [ "$backup_existing" = "true" ]; then
  backup_root="$target_root_abs.ai-system-install-backups/$(date +%Y%m%d%H%M%S)-$$"
  move_to_backup "$core_agents_dst" "$backup_root/AGENTS.md"
  move_to_backup "$core_ai_system_dst" "$backup_root/ai-system"
fi

copy_core
import_agent_context

if [ -n "$codex_home_abs" ]; then
  installer="$PACKAGE_ROOT/implementation-packs/codex-safety-net/scripts/install-safety-net.sh"
  require_source "$installer"

  set -- "$installer" --workspace "$target_root_abs" --codex-home "$codex_home_abs" --apply
  if [ -n "$codex_bin" ]; then
    set -- "$@" --codex-bin "$codex_bin"
  fi
  if [ "$backup_existing" = "true" ]; then
    set -- "$@" --backup-existing
  fi
  "$@"
fi
