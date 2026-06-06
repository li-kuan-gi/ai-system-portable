#!/usr/bin/env sh
set -eu

usage() {
  cat <<'USAGE'
Usage:
  install-safety-net.sh --workspace <path> [options]

Installs the Claude Code safety-net implementation pack into <workspace>/.claude:
  - hooks/allow_trusted_script_permission.py
  - hooks/allow_worktree_edit_permission.py
  - portable-claude-safety-net.settings.snippet.json (resolved snippet for manual merge)
  - settings.json when it is missing, empty, or already references this safety net

This script does not modify settings.local.json, auth, sessions, logs, or cache.
By default, --apply refuses to overwrite existing hook files. Existing settings.json
is replaced only when it already references this safety net, is empty, or
--backup-existing is provided; otherwise merge the resolved snippet manually.

Options:
  --dry-run           Print planned changes. Default.
  --apply             Install files.
  --backup-existing   Back up existing targets before replacing them.
USAGE
}

workspace=
mode=dry-run
backup_existing=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --workspace)
      workspace=${2:-}
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

if [ -z "$workspace" ]; then
  usage >&2
  exit 2
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PACK_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

abspath() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "$(pwd)" "$1" ;;
  esac
}

trusted_hook_src="$PACK_DIR/hooks/allow_trusted_script_permission.py"
worktree_hook_src="$PACK_DIR/hooks/allow_worktree_edit_permission.py"
snippet_src="$PACK_DIR/templates/settings.snippet.json"
workspace_abs=$(abspath "$workspace")

claude_dir="$workspace_abs/.claude"
hooks_dir="$claude_dir/hooks"
trusted_hook_dst="$hooks_dir/allow_trusted_script_permission.py"
worktree_hook_dst="$hooks_dir/allow_worktree_edit_permission.py"
resolved_snippet_dst="$claude_dir/portable-claude-safety-net.settings.snippet.json"
settings_dst="$claude_dir/settings.json"

if [ ! -f "$trusted_hook_src" ] || [ ! -f "$worktree_hook_src" ] || [ ! -f "$snippet_src" ]; then
  echo "pack files are missing" >&2
  exit 2
fi

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

backup_file() {
  src=$1
  dst=$2
  if path_exists "$src"; then
    mkdir -p "$(dirname -- "$dst")"
    cp -p "$src" "$dst"
    echo "backup: $src -> $dst"
  fi
}

settings_has_safety_net() {
  file=$1
  [ -f "$file" ] \
    && grep -F "allow_trusted_script_permission.py" "$file" >/dev/null 2>&1 \
    && grep -F "$workspace_abs" "$file" >/dev/null 2>&1
}

sed_replacement_escape() {
  printf '%s' "$1" | sed 's/[\/&]/\\&/g'
}

write_resolved_snippet() {
  workspace_escaped=$(sed_replacement_escape "$workspace_abs")
  sed -e "s/<WORKSPACE_ROOT>/$workspace_escaped/g" "$snippet_src" > "$resolved_snippet_dst"
  chmod 0644 "$resolved_snippet_dst"
  echo "installed resolved settings snippet: $resolved_snippet_dst"
}

echo "workspace=$workspace_abs"
echo "mode=$mode"
echo "backup_existing=$backup_existing"
echo "install hook: $trusted_hook_src -> $trusted_hook_dst"
echo "target hook status: $(target_status "$trusted_hook_dst")"
echo "install hook: $worktree_hook_src -> $worktree_hook_dst"
echo "target hook status: $(target_status "$worktree_hook_dst")"
echo "install resolved snippet: $snippet_src -> $resolved_snippet_dst"
echo "target resolved snippet status: $(target_status "$resolved_snippet_dst")"
echo "install settings.json: $resolved_snippet_dst -> $settings_dst"
echo "target settings.json status: $(target_status "$settings_dst")"

if [ "$mode" = "dry-run" ]; then
  exit 0
fi

if path_exists "$settings_dst" \
  && ! settings_has_safety_net "$settings_dst" \
  && [ -s "$settings_dst" ] \
  && [ "$backup_existing" != "true" ]; then
  echo "target settings.json already exists and does not reference this safety net; rerun with --backup-existing to back it up and replace it, or merge $resolved_snippet_dst manually: $settings_dst" >&2
  exit 2
fi

if path_exists "$trusted_hook_dst" || path_exists "$worktree_hook_dst" || path_exists "$resolved_snippet_dst"; then
  if [ "$backup_existing" != "true" ]; then
    echo "target hook/snippet files already exist; rerun with --backup-existing to back up before overwrite" >&2
    exit 2
  fi
fi

if [ "$backup_existing" = "true" ]; then
  backup_root="$claude_dir/backups/safety-net/$(date +%Y%m%d%H%M%S)-$$"
  backup_file "$trusted_hook_dst" "$backup_root/hooks/allow_trusted_script_permission.py"
  backup_file "$worktree_hook_dst" "$backup_root/hooks/allow_worktree_edit_permission.py"
  backup_file "$resolved_snippet_dst" "$backup_root/portable-claude-safety-net.settings.snippet.json"
  backup_file "$settings_dst" "$backup_root/settings.json"
fi

mkdir -p "$hooks_dir"
cp "$trusted_hook_src" "$trusted_hook_dst"
cp "$worktree_hook_src" "$worktree_hook_dst"
chmod 0755 "$trusted_hook_dst" "$worktree_hook_dst"
write_resolved_snippet

if ! path_exists "$settings_dst" || [ ! -s "$settings_dst" ] || [ "$backup_existing" = "true" ]; then
  cp "$resolved_snippet_dst" "$settings_dst"
  chmod 0644 "$settings_dst"
  echo "installed settings.json: $settings_dst"
elif settings_has_safety_net "$settings_dst"; then
  echo "settings.json already references this safety net: $settings_dst"
fi

echo "installed safety-net files; settings.json is ready at $settings_dst"
if [ "${backup_root:-}" ]; then
  echo "backup_root=$backup_root"
fi
