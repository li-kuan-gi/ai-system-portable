#!/usr/bin/env sh
set -eu

usage() {
  cat <<'USAGE'
Usage:
  install-claude-portable.sh --target-root <path> [options]

One-step Claude Code import. Installs:
  - portable core (AGENTS.md + ai-system) into <target-root>
  - CLAUDE.md entry into <target-root>
  - Claude safety-net hooks + settings.json into <target-root>/.claude

This is a thin orchestrator over:
  - scripts/install-portable-system.sh                          (portable core)
  - implementation-packs/claude-safety-net/scripts/install-safety-net.sh  (Claude safety net)

It does not modify .claude/settings.local.json, auth, sessions, logs, or cache.

Options:
  --agent-history-file <path>   Import agent-readable conversation history markdown
  --agent-settings-file <path>  Import agent-readable settings markdown
  --dry-run                     Print planned changes. Default.
  --apply                       Install the portable core, CLAUDE.md, and Claude safety net.
  --backup-existing             Back up existing targets before replacing them.
USAGE
}

target_root=
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

target_root_abs=$(abspath "$target_root")
core_installer="$PACKAGE_ROOT/scripts/install-portable-system.sh"
claude_installer="$PACKAGE_ROOT/implementation-packs/claude-safety-net/scripts/install-safety-net.sh"
claude_md_src="$PACKAGE_ROOT/service-packs/claude-code/templates/CLAUDE.md"
claude_md_dst="$target_root_abs/CLAUDE.md"

for f in "$core_installer" "$claude_installer" "$claude_md_src"; do
  if [ ! -f "$f" ]; then
    echo "missing package file: $f" >&2
    exit 2
  fi
done

path_exists() {
  [ -e "$1" ] || [ -L "$1" ]
}

target_status() {
  if path_exists "$1"; then
    echo "exists"
  else
    echo "missing"
  fi
}

# Build pass-through flags for the sub-installers.
mode_flag=--dry-run
[ "$mode" = "apply" ] && mode_flag=--apply
backup_flag=
[ "$backup_existing" = "true" ] && backup_flag=--backup-existing

echo "target_root=$target_root_abs"
echo "mode=$mode"
echo "backup_existing=$backup_existing"
echo "install CLAUDE.md: $claude_md_src -> $claude_md_dst"
echo "target CLAUDE.md status: $(target_status "$claude_md_dst")"
echo ""

echo "=== step 1/3: portable core ==="
core_args="--target-root $target_root_abs $mode_flag"
[ -n "$backup_flag" ] && core_args="$core_args $backup_flag"
[ -n "$agent_history_file" ] && core_args="$core_args --agent-history-file $agent_history_file"
[ -n "$agent_settings_file" ] && core_args="$core_args --agent-settings-file $agent_settings_file"
# shellcheck disable=SC2086
sh "$core_installer" $core_args

echo ""
echo "=== step 2/3: CLAUDE.md entry ==="
if [ "$mode" = "dry-run" ]; then
  echo "(dry-run) would install $claude_md_src -> $claude_md_dst"
else
  if path_exists "$claude_md_dst" && [ "$backup_existing" != "true" ]; then
    echo "target CLAUDE.md already exists; rerun with --backup-existing to back it up before replacing: $claude_md_dst" >&2
    exit 2
  fi
  if path_exists "$claude_md_dst" && [ "$backup_existing" = "true" ]; then
    backup_root="$target_root_abs.ai-system-install-backups/$(date +%Y%m%d%H%M%S)-$$"
    mkdir -p "$backup_root"
    cp -p "$claude_md_dst" "$backup_root/CLAUDE.md"
    echo "backup: $claude_md_dst -> $backup_root/CLAUDE.md"
  fi
  cp "$claude_md_src" "$claude_md_dst"
  echo "installed CLAUDE.md: $claude_md_dst"
fi

echo ""
echo "=== step 3/3: Claude safety net ==="
claude_args="--workspace $target_root_abs $mode_flag"
[ -n "$backup_flag" ] && claude_args="$claude_args $backup_flag"
# shellcheck disable=SC2086
sh "$claude_installer" $claude_args

echo ""
if [ "$mode" = "dry-run" ]; then
  echo "dry-run complete; rerun with --apply to install."
else
  echo "Claude Code import complete. Open Claude Code from $target_root_abs."
  echo "git and gh are already in the neutral default. If the target workspace uses kubectl / helm / argocd, merge:"
  echo "  $PACKAGE_ROOT/implementation-packs/claude-safety-net/templates/settings.devops-readonly.example.json"
fi
