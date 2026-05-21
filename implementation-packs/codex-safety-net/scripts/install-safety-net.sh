#!/usr/bin/env sh
set -eu

usage() {
  cat <<'USAGE'
Usage:
  install-safety-net.sh --workspace <path> --codex-home <path> [options]

Installs the Codex safety-net implementation pack:
  - hooks/allow_trusted_script_permission.py
  - rules/minimal.rules
  - templates/portable-codex-safety-net.config.snippet.toml
  - templates/portable-codex-safety-net.config.resolved.toml when --codex-bin is provided
  - config.toml when --codex-bin is provided and config.toml is missing or safely replaceable

This script does not modify auth, secrets, sessions, logs, or cache.
By default, --apply refuses to overwrite existing hook/rules/snippet files.
Existing config.toml is replaced only when it already references this safety net,
is empty, or --backup-existing is provided.

Options:
  --codex-bin <path|name>  Codex binary path used to materialize the resolved config snippet
  --dry-run                Print planned changes. Default.
  --apply                  Install files.
  --backup-existing        Back up existing targets before replacing them.
USAGE
}

workspace=
codex_home=
codex_bin=
mode=dry-run
backup_existing=false

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

if [ -z "$workspace" ] || [ -z "$codex_home" ]; then
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

resolve_codex_bin() {
  raw=$1
  case "$raw" in
    */*)
      resolved=$(abspath "$raw")
      ;;
    *)
      resolved=$(command -v "$raw" 2>/dev/null || true)
      if [ -z "$resolved" ]; then
        echo "Codex binary not found in PATH: $raw. Install Codex CLI first, ensure it is on PATH, or rerun with --codex-bin <path>." >&2
        exit 2
      fi
      ;;
  esac

  if [ ! -x "$resolved" ]; then
    echo "Codex binary is not executable: $resolved" >&2
    exit 2
  fi
  printf '%s\n' "$resolved"
}

canonical_existing_path() {
  path=$1
  dir=$(dirname -- "$path")
  base=$(basename -- "$path")
  if [ -d "$dir" ]; then
    printf '%s/%s\n' "$(CDPATH= cd -- "$dir" && pwd -P)" "$base"
  else
    printf '%s\n' "$path"
  fi
}

resolve_symlink_target() {
  path=$1
  while [ -L "$path" ]; do
    link=$(readlink "$path")
    case "$link" in
      /*) path=$link ;;
      *) path=$(dirname -- "$path")/$link ;;
    esac
  done
  canonical_existing_path "$path"
}

resolve_codex_runtime_read_path() {
  real_bin=$(resolve_symlink_target "$1")
  bin_dir=$(dirname -- "$real_bin")
  package_dir=$(dirname -- "$bin_dir")

  if [ "$(basename -- "$bin_dir")" = "bin" ] && [ -f "$package_dir/package.json" ]; then
    (CDPATH= cd -- "$package_dir" && pwd -P)
  else
    printf '%s\n' "$1"
  fi
}

hook_src="$PACK_DIR/hooks/allow_trusted_script_permission.py"
rules_src="$PACK_DIR/rules/minimal.rules"
snippet_src="$PACK_DIR/templates/config.snippet.toml"
workspace_abs=$(abspath "$workspace")
codex_home_abs=$(abspath "$codex_home")
codex_bin_abs=
codex_runtime_read_path=
if [ -n "$codex_bin" ]; then
  codex_bin_abs=$(resolve_codex_bin "$codex_bin")
  codex_runtime_read_path=$(resolve_codex_runtime_read_path "$codex_bin_abs")
fi
hook_dst="$codex_home_abs/hooks/allow_trusted_script_permission.py"
rules_dst="$codex_home_abs/rules/minimal.rules"
snippet_dst="$codex_home_abs/templates/portable-codex-safety-net.config.snippet.toml"
resolved_snippet_dst="$codex_home_abs/templates/portable-codex-safety-net.config.resolved.toml"
config_dst="$codex_home_abs/config.toml"

if [ ! -f "$hook_src" ] || [ ! -f "$rules_src" ] || [ ! -f "$snippet_src" ]; then
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

config_has_safety_net() {
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
  codex_home_escaped=$(sed_replacement_escape "$codex_home_abs")
  codex_runtime_read_path_escaped=$(sed_replacement_escape "$codex_runtime_read_path")
  sed \
    -e "s/<WORKSPACE_ROOT>/$workspace_escaped/g" \
    -e "s/<CODEX_HOME>/$codex_home_escaped/g" \
    -e "s/<CODEX_RUNTIME_READ_PATH>/$codex_runtime_read_path_escaped/g" \
    "$snippet_src" > "$resolved_snippet_dst"
  chmod 0644 "$resolved_snippet_dst"
  echo "installed resolved config snippet: $resolved_snippet_dst"
}

echo "workspace=$workspace_abs"
echo "codex_home=$codex_home_abs"
if [ -n "$codex_bin_abs" ]; then
  echo "codex_bin=$codex_bin_abs"
  echo "codex_runtime_read_path=$codex_runtime_read_path"
else
  echo "codex_bin=(not provided; skip resolved config snippet)"
fi
echo "mode=$mode"
echo "backup_existing=$backup_existing"
echo "install hook: $hook_src -> $hook_dst"
echo "target hook status: $(target_status "$hook_dst")"
echo "install rules: $rules_src -> $rules_dst"
echo "target rules status: $(target_status "$rules_dst")"
echo "install config snippet: $snippet_src -> $snippet_dst"
echo "target config snippet status: $(target_status "$snippet_dst")"
if [ -n "$codex_bin_abs" ]; then
  echo "install resolved config snippet: $snippet_src -> $resolved_snippet_dst"
  echo "target resolved config snippet status: $(target_status "$resolved_snippet_dst")"
  echo "install config.toml: $resolved_snippet_dst -> $config_dst"
  echo "target config.toml status: $(target_status "$config_dst")"
fi

if [ "$mode" = "dry-run" ]; then
  exit 0
fi

if [ -n "$codex_bin_abs" ] \
  && path_exists "$config_dst" \
  && ! config_has_safety_net "$config_dst" \
  && [ -s "$config_dst" ] \
  && [ "$backup_existing" != "true" ]; then
  echo "target config.toml already exists and does not reference this safety net; rerun with --backup-existing to back it up and replace it, or merge $resolved_snippet_dst manually: $config_dst" >&2
  exit 2
fi

if path_exists "$hook_dst" || path_exists "$rules_dst" || path_exists "$snippet_dst" || { [ -n "$codex_bin_abs" ] && path_exists "$resolved_snippet_dst"; }; then
  if [ "$backup_existing" != "true" ]; then
    echo "target hook/rules/snippet already exist; rerun with --backup-existing to back up before overwrite" >&2
    exit 2
  fi
fi

if [ "$backup_existing" = "true" ]; then
  backup_root="$codex_home_abs/backups/safety-net/$(date +%Y%m%d%H%M%S)-$$"
  backup_file "$hook_dst" "$backup_root/hooks/allow_trusted_script_permission.py"
  backup_file "$rules_dst" "$backup_root/rules/minimal.rules"
  backup_file "$snippet_dst" "$backup_root/templates/portable-codex-safety-net.config.snippet.toml"
  backup_file "$resolved_snippet_dst" "$backup_root/templates/portable-codex-safety-net.config.resolved.toml"
  backup_file "$config_dst" "$backup_root/config.toml"
fi

mkdir -p "$codex_home_abs/hooks" "$codex_home_abs/rules" "$codex_home_abs/templates"
cp "$hook_src" "$hook_dst"
cp "$rules_src" "$rules_dst"
cp "$snippet_src" "$snippet_dst"
chmod 0755 "$hook_dst"
chmod 0644 "$rules_dst"
chmod 0644 "$snippet_dst"
if [ -n "$codex_bin_abs" ]; then
  write_resolved_snippet
fi

if [ -n "$codex_bin_abs" ]; then
  if ! path_exists "$config_dst" || [ ! -s "$config_dst" ] || [ "$backup_existing" = "true" ]; then
    cp "$resolved_snippet_dst" "$config_dst"
    chmod 0600 "$config_dst"
    echo "installed config.toml: $config_dst"
  elif config_has_safety_net "$config_dst"; then
    echo "config.toml already references this safety net: $config_dst"
  fi
  echo "installed safety-net files; config.toml is ready at $config_dst"
else
  echo "installed safety-net files; merge $snippet_dst into config.toml manually"
fi
if [ "${backup_root:-}" ]; then
  echo "backup_root=$backup_root"
fi
