#!/usr/bin/env sh
set -eu

usage() {
  cat <<'USAGE'
Usage:
  install-codex-command.sh --workspace <path> --codex-home <path> --command-name <name> [options]

Options:
  --bin-dir <path>          Directory for the generated command. Default: $HOME/.local/bin
  --codex-bin <path|name>   Codex binary used by the generated command. Default: auto-detect codex
  --shell-rc <path>         Append an alias line to a shell rc file, such as $HOME/.bashrc
  --dry-run                 Print planned changes. Default.
  --apply                   Create the command and optionally append shell rc alias.
  --backup-existing         Back up an existing generated command before replacing it.
  --skip-safety-net-check   Do not require Codex safety-net files to exist at install time.

Creates a dedicated command that starts Codex from a fixed workspace root with
a fixed CODEX_HOME.
USAGE
}

workspace=
codex_home=
command_name=
bin_dir=${HOME:-}/.local/bin
codex_bin=${CODEX_BIN:-codex}
shell_rc=
mode=dry-run
backup_existing=false
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
    --command-name)
      command_name=${2:-}
      shift 2
      ;;
    --bin-dir)
      bin_dir=${2:-}
      shift 2
      ;;
    --codex-bin)
      codex_bin=${2:-}
      shift 2
      ;;
    --shell-rc)
      shell_rc=${2:-}
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
    --skip-safety-net-check)
      skip_safety_net_check=true
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

if [ -z "$workspace" ] || [ -z "$codex_home" ] || [ -z "$command_name" ]; then
  usage >&2
  exit 2
fi

case "$command_name" in
  .*|*/*|*\'*|*\"*|*=*|*' '*|*'	'*|"")
    echo "command name must be a simple command segment without slash, quotes, equals, spaces, or leading dot" >&2
    exit 2
    ;;
esac

abspath() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "$(pwd)" "$1" ;;
  esac
}

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

fail() {
  echo "$*" >&2
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

shell_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")"
}

resolve_install_codex_bin() {
  raw=$1
  case "$raw" in
    */*)
      resolved=$(abspath "$raw")
      ;;
    *)
      resolved=$(command -v "$raw" 2>/dev/null || true)
      if [ -z "$resolved" ]; then
        fail "Codex binary not found in PATH: $raw. Install Codex CLI first, ensure it is on PATH, or rerun with --codex-bin <path>."
      fi
      ;;
  esac

  if [ ! -x "$resolved" ]; then
    fail "Codex binary is not executable: $resolved"
  fi
  printf '%s\n' "$resolved"
}

write_launcher() {
  dst=$1
  tmp=$dst.tmp.$$
  {
    echo "#!/usr/bin/env sh"
    echo "set -eu"
    echo "WORKSPACE_ROOT=$(shell_quote "$workspace_abs")"
    echo "CODEX_HOME_VALUE=$(shell_quote "$codex_home_abs")"
    echo "CODEX_BIN_VALUE=$(shell_quote "$codex_bin")"
    echo "SKIP_SAFETY_NET_CHECK=$(shell_quote "$skip_safety_net_check")"
    cat <<'LAUNCHER'

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

warn() {
  echo "warning: $*" >&2
}

resolve_codex_bin() {
  raw=$1
  case "$raw" in
    */*)
      if [ ! -x "$raw" ]; then
        fail "codex binary is not executable: $raw"
      fi
      printf '%s\n' "$raw"
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

require_dir "$WORKSPACE_ROOT"
require_file "$WORKSPACE_ROOT/AGENTS.md"
require_file "$WORKSPACE_ROOT/ai-system/entry.md"

if [ "$SKIP_SAFETY_NET_CHECK" != "true" ]; then
  require_dir "$CODEX_HOME_VALUE"
  require_file "$CODEX_HOME_VALUE/hooks/allow_trusted_script_permission.py"
  require_file "$CODEX_HOME_VALUE/rules/minimal.rules"
  require_file "$CODEX_HOME_VALUE/templates/portable-codex-safety-net.config.snippet.toml"
fi

config_snippet="$CODEX_HOME_VALUE/templates/portable-codex-safety-net.config.resolved.toml"
if [ ! -f "$config_snippet" ]; then
  config_snippet="$CODEX_HOME_VALUE/templates/portable-codex-safety-net.config.snippet.toml"
fi

if [ ! -f "$CODEX_HOME_VALUE/config.toml" ]; then
  warn "$CODEX_HOME_VALUE/config.toml not found; merge $config_snippet before relying on the safety net"
else
  if ! grep -F "allow_trusted_script_permission.py" "$CODEX_HOME_VALUE/config.toml" >/dev/null 2>&1; then
    warn "$CODEX_HOME_VALUE/config.toml does not appear to reference allow_trusted_script_permission.py; merge $config_snippet"
  fi
  if ! grep -F "$WORKSPACE_ROOT" "$CODEX_HOME_VALUE/config.toml" >/dev/null 2>&1; then
    warn "$CODEX_HOME_VALUE/config.toml does not appear to reference workspace: $WORKSPACE_ROOT; merge $config_snippet"
  fi
fi

codex_bin_resolved=$(resolve_codex_bin "$CODEX_BIN_VALUE")
cd "$WORKSPACE_ROOT"
export CODEX_HOME="$CODEX_HOME_VALUE"
exec "$codex_bin_resolved" "$@"
LAUNCHER
  } > "$tmp"
  chmod 0755 "$tmp"
  mv "$tmp" "$dst"
}

append_shell_rc() {
  rc=$1
  alias_line="alias $command_name=$(shell_quote "$command_path")"
  marker="# ai-system-portable codex command: $command_name"

  if [ -f "$rc" ] && grep -F "$marker" "$rc" >/dev/null 2>&1; then
    echo "shell rc already contains launcher marker: $rc"
    return 0
  fi

  if [ "$backup_existing" = "true" ] && [ -f "$rc" ]; then
    cp -p "$rc" "$rc.ai-system-portable-backup.$(date +%Y%m%d%H%M%S)-$$"
  fi

  mkdir -p "$(dirname -- "$rc")"
  {
    echo ""
    echo "$marker"
    echo "$alias_line"
  } >> "$rc"
  echo "appended shell alias to $rc"
  echo "reload the shell or source $rc before using alias: $command_name"
}

workspace_abs=$(abspath "$workspace")
codex_home_abs=$(abspath "$codex_home")
bin_dir_abs=$(abspath "$bin_dir")
codex_bin=$(resolve_install_codex_bin "$codex_bin")
command_path="$bin_dir_abs/$command_name"
shell_rc_abs=
if [ -n "$shell_rc" ]; then
  shell_rc_abs=$(abspath "$shell_rc")
fi

echo "workspace=$workspace_abs"
echo "codex_home=$codex_home_abs"
echo "codex_bin=$codex_bin"
echo "command_name=$command_name"
echo "command_path=$command_path"
echo "mode=$mode"
echo "backup_existing=$backup_existing"
echo "skip_safety_net_check=$skip_safety_net_check"
echo "workspace AGENTS.md status: $(target_status "$workspace_abs/AGENTS.md")"
echo "workspace ai-system/entry.md status: $(target_status "$workspace_abs/ai-system/entry.md")"
if [ "$skip_safety_net_check" != "true" ]; then
  echo "codex hook status: $(target_status "$codex_home_abs/hooks/allow_trusted_script_permission.py")"
  echo "codex rules status: $(target_status "$codex_home_abs/rules/minimal.rules")"
  echo "codex config snippet status: $(target_status "$codex_home_abs/templates/portable-codex-safety-net.config.snippet.toml")"
fi
if [ -n "$shell_rc_abs" ]; then
  echo "shell_rc=$shell_rc_abs"
fi

if [ "$mode" = "dry-run" ]; then
  echo "would create command: $command_path"
  if [ -n "$shell_rc_abs" ]; then
    echo "would append shell alias to: $shell_rc_abs"
  fi
  exit 0
fi

require_dir "$workspace_abs"
require_file "$workspace_abs/AGENTS.md"
require_file "$workspace_abs/ai-system/entry.md"

if [ "$skip_safety_net_check" != "true" ]; then
  require_dir "$codex_home_abs"
  require_file "$codex_home_abs/hooks/allow_trusted_script_permission.py"
  require_file "$codex_home_abs/rules/minimal.rules"
  require_file "$codex_home_abs/templates/portable-codex-safety-net.config.snippet.toml"
fi

mkdir -p "$bin_dir_abs"

if path_exists "$command_path"; then
  if [ "$backup_existing" != "true" ]; then
    echo "target command already exists; rerun with --backup-existing to back it up before overwrite: $command_path" >&2
    exit 2
  fi
  backup_root="$bin_dir_abs.ai-system-launcher-backups/$(date +%Y%m%d%H%M%S)-$$"
  mkdir -p "$backup_root"
  mv "$command_path" "$backup_root/$command_name"
  echo "backup: $command_path -> $backup_root/$command_name"
fi

write_launcher "$command_path"
echo "installed codex command: $command_path"

if [ -n "$shell_rc_abs" ]; then
  append_shell_rc "$shell_rc_abs"
fi
