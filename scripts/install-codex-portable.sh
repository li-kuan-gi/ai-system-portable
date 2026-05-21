#!/usr/bin/env sh
set -eu

usage() {
  cat <<'USAGE'
Usage:
  install-codex-portable.sh --target-root <path> --codex-home <path> --command-name <name> [options]

Options:
  --bin-dir <path>             Directory for the generated command. Default: $HOME/.local/bin
  --codex-bin <path|name>      Codex binary. Default: auto-detect codex in PATH
  --shell-rc <path>            Append an alias line to a shell rc file, such as $HOME/.bashrc
  --agent-history-file <path>  Import agent-readable conversation history / handoff markdown
  --agent-settings-file <path> Import agent-readable settings markdown
  --confirm-no-shell-rc        Confirm intentionally not writing a shell rc alias in non-interactive use
  --dry-run                    Print planned changes. Default.
  --apply                      Install the portable system and generated Codex command.
  --backup-existing            Back up existing targets before replacing them.

Installs:
  - portable core into <target-root>
  - Codex safety-net files into <codex-home>
  - Codex config.toml when it is missing or safely replaceable
  - one fixed Codex launcher command that starts from <target-root> with <codex-home>

When --shell-rc is omitted, --apply asks for explicit confirmation. In
non-interactive use, pass --confirm-no-shell-rc or provide --shell-rc.
USAGE
}

target_root=
codex_home=
command_name=
bin_dir=${HOME:-}/.local/bin
codex_bin=${CODEX_BIN:-codex}
shell_rc=
agent_history_file=
agent_settings_file=
mode=dry-run
backup_existing=false
confirm_no_shell_rc=false

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
    --agent-history-file)
      agent_history_file=${2:-}
      shift 2
      ;;
    --agent-settings-file)
      agent_settings_file=${2:-}
      shift 2
      ;;
    --confirm-no-shell-rc)
      confirm_no_shell_rc=true
      shift
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

if [ -z "$target_root" ] || [ -z "$codex_home" ] || [ -z "$command_name" ]; then
  usage >&2
  exit 2
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PACKAGE_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PORTABLE_INSTALLER="$SCRIPT_DIR/install-portable-system.sh"
COMMAND_INSTALLER="$SCRIPT_DIR/install-codex-command.sh"

abspath() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "$(pwd)" "$1" ;;
  esac
}

fail() {
  echo "$*" >&2
  exit 2
}

require_source() {
  if [ ! -f "$1" ]; then
    fail "package source is missing: $1"
  fi
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

resolve_codex_bin() {
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

confirm_without_shell_rc() {
  if [ ! -t 0 ]; then
    fail "No --shell-rc was provided and stdin is not interactive. Rerun with --shell-rc <path>, or pass --confirm-no-shell-rc to intentionally skip shell rc alias installation."
  fi

  printf '%s' "No --shell-rc was provided. Continue without installing a shell alias? Type yes to continue: " >&2
  IFS= read -r answer
  if [ "$answer" != "yes" ]; then
    fail "aborted because shell rc alias installation was not confirmed"
  fi
}

preflight_apply_conflicts() {
  if [ "$mode" != "apply" ] || [ "$backup_existing" = "true" ]; then
    return 0
  fi

  conflict=false
  if path_exists "$target_root_abs/AGENTS.md"; then
    echo "target already exists: $target_root_abs/AGENTS.md" >&2
    conflict=true
  fi
  if path_exists "$target_root_abs/ai-system"; then
    echo "target already exists: $target_root_abs/ai-system" >&2
    conflict=true
  fi
  if path_exists "$codex_home_abs/hooks/allow_trusted_script_permission.py"; then
    echo "target already exists: $codex_home_abs/hooks/allow_trusted_script_permission.py" >&2
    conflict=true
  fi
  if path_exists "$codex_home_abs/rules/minimal.rules"; then
    echo "target already exists: $codex_home_abs/rules/minimal.rules" >&2
    conflict=true
  fi
  if path_exists "$codex_home_abs/templates/portable-codex-safety-net.config.snippet.toml"; then
    echo "target already exists: $codex_home_abs/templates/portable-codex-safety-net.config.snippet.toml" >&2
    conflict=true
  fi
  if path_exists "$codex_home_abs/templates/portable-codex-safety-net.config.resolved.toml"; then
    echo "target already exists: $codex_home_abs/templates/portable-codex-safety-net.config.resolved.toml" >&2
    conflict=true
  fi
  if path_exists "$codex_home_abs/config.toml" \
    && ! config_has_safety_net "$codex_home_abs/config.toml" \
    && [ -s "$codex_home_abs/config.toml" ]; then
    echo "target config.toml already exists and does not reference this safety net: $codex_home_abs/config.toml" >&2
    conflict=true
  fi
  if path_exists "$bin_dir_abs/$command_name"; then
    echo "target already exists: $bin_dir_abs/$command_name" >&2
    conflict=true
  fi

  if [ "$conflict" = "true" ]; then
    fail "existing targets detected; rerun with --backup-existing to back them up before install"
  fi
}

run_portable_installer() {
  set -- "$PORTABLE_INSTALLER" \
    --target-root "$target_root_abs" \
    --codex-home "$codex_home_abs" \
    --codex-bin "$codex_bin_resolved" \
    "$mode_arg"

  if [ -n "$agent_history_file_abs" ]; then
    set -- "$@" --agent-history-file "$agent_history_file_abs"
  fi
  if [ -n "$agent_settings_file_abs" ]; then
    set -- "$@" --agent-settings-file "$agent_settings_file_abs"
  fi
  if [ "$backup_existing" = "true" ]; then
    set -- "$@" --backup-existing
  fi
  "$@"
}

run_command_installer() {
  if [ -n "$shell_rc_abs" ]; then
    if [ "$backup_existing" = "true" ]; then
      "$COMMAND_INSTALLER" \
        --workspace "$target_root_abs" \
        --codex-home "$codex_home_abs" \
        --command-name "$command_name" \
        --bin-dir "$bin_dir_abs" \
        --codex-bin "$codex_bin_resolved" \
        --shell-rc "$shell_rc_abs" \
        "$mode_arg" \
        --backup-existing
    else
      "$COMMAND_INSTALLER" \
        --workspace "$target_root_abs" \
        --codex-home "$codex_home_abs" \
        --command-name "$command_name" \
        --bin-dir "$bin_dir_abs" \
        --codex-bin "$codex_bin_resolved" \
        --shell-rc "$shell_rc_abs" \
        "$mode_arg"
    fi
  else
    if [ "$backup_existing" = "true" ]; then
      "$COMMAND_INSTALLER" \
        --workspace "$target_root_abs" \
        --codex-home "$codex_home_abs" \
        --command-name "$command_name" \
        --bin-dir "$bin_dir_abs" \
        --codex-bin "$codex_bin_resolved" \
        "$mode_arg" \
        --backup-existing
    else
      "$COMMAND_INSTALLER" \
        --workspace "$target_root_abs" \
        --codex-home "$codex_home_abs" \
        --command-name "$command_name" \
        --bin-dir "$bin_dir_abs" \
        --codex-bin "$codex_bin_resolved" \
        "$mode_arg"
    fi
  fi
}

record_codex_agent_settings() {
  if [ "$mode" != "apply" ]; then
    return 0
  fi

  settings_file="$target_root_abs/ai-system/knowledge/context/agent-settings.md"
  if [ ! -f "$settings_file" ]; then
    return 0
  fi

  {
    echo ""
    echo "## Codex Launcher Settings"
    echo ""
    echo "- **來源**：scripts/install-codex-portable.sh --apply"
    echo "- **查證狀態**：安裝腳本於 $(date +%Y-%m-%d) 寫入"
    echo "- **workspace root**：$target_root_abs"
    echo "- **CODEX_HOME**：$codex_home_abs"
    echo "- **Codex binary**：$codex_bin_resolved"
    echo "- **Codex runtime read path**：$codex_runtime_read_path"
    echo "- **launcher command**：$bin_dir_abs/$command_name"
    if [ -n "$shell_rc_abs" ]; then
      echo "- **shell rc alias**：$shell_rc_abs"
    else
      echo "- **shell rc alias**：未安裝"
    fi
    echo "- **config snippet**：$codex_home_abs/templates/portable-codex-safety-net.config.resolved.toml"
    echo "- **generic config snippet**：$codex_home_abs/templates/portable-codex-safety-net.config.snippet.toml"
    echo "- **config.toml**：$codex_home_abs/config.toml"
    echo "- **sandbox note**：workspace permission must allow the Codex runtime read path. For npm-style installs, the launcher can be a symlink into a package that later executes native vendor files under that package, so allowing only the launcher shim is insufficient."
    echo ""
    echo "### Codex Service Storage Map"
    echo ""
    echo "- **設定檔**：$codex_home_abs/config.toml"
    echo "- **對話 sessions**：$codex_home_abs/sessions/"
    echo "- **歷史索引**：$codex_home_abs/history.jsonl"
    echo "- **memories**：$codex_home_abs/memories/"
    echo "- **hooks**：$codex_home_abs/hooks/"
    echo "- **rules**：$codex_home_abs/rules/"
    echo "- **runtime logs**：$codex_home_abs/log/ 與 $codex_home_abs/logs_*.sqlite"
    echo "- **runtime state / cache**：$codex_home_abs/state_*.sqlite、$codex_home_abs/cache/、$codex_home_abs/tmp/"
    echo "- **shell snapshots**：$codex_home_abs/shell_snapshots/"
    echo "- **auth / secrets 禁止讀取內容**：$codex_home_abs/auth.json、$codex_home_abs/secrets/"
    echo "- **讀取規則**：需要延續歷史脈絡或查 runtime 設定時才讀 sessions/history/config；優先摘要，不複製 raw transcript；不得讀取 auth / secrets 內容。"
  } >> "$settings_file"
  echo "recorded Codex launcher settings: $settings_file"
}

print_config_next_step() {
  if [ "$mode" != "apply" ]; then
    return 0
  fi

  config_file="$codex_home_abs/config.toml"
  resolved_snippet="$codex_home_abs/templates/portable-codex-safety-net.config.resolved.toml"
  generic_snippet="$codex_home_abs/templates/portable-codex-safety-net.config.snippet.toml"
  if [ ! -f "$resolved_snippet" ]; then
    resolved_snippet="$generic_snippet"
  fi

  if config_has_safety_net "$config_file"; then
    echo "codex config appears to reference the portable safety-net hook: $config_file"
    return 0
  fi

  echo ""
  echo "NEXT STEP: merge Codex safety-net config into:"
  echo "  $config_file"
  echo "Use this snippet:"
  echo "  $resolved_snippet"
  echo "If this CODEX_HOME is dedicated and config.toml has no custom settings to preserve, back up then replace it:"
  echo "  cp -p \"$config_file\" \"$config_file.bak-\$(date +%Y%m%d%H%M%S)\""
  echo "  cp -p \"$resolved_snippet\" \"$config_file\""
  echo "Otherwise merge the snippet manually; do not overwrite unrelated config."
}

require_source "$PORTABLE_INSTALLER"
require_source "$COMMAND_INSTALLER"

case "$mode" in
  dry-run) mode_arg=--dry-run ;;
  apply) mode_arg=--apply ;;
  *) fail "unknown mode: $mode" ;;
esac

target_root_abs=$(abspath "$target_root")
codex_home_abs=$(abspath "$codex_home")
bin_dir_abs=$(abspath "$bin_dir")
codex_bin_resolved=$(resolve_codex_bin "$codex_bin")
codex_runtime_read_path=$(resolve_codex_runtime_read_path "$codex_bin_resolved")
shell_rc_abs=
if [ -n "$shell_rc" ]; then
  shell_rc_abs=$(abspath "$shell_rc")
fi
agent_history_file_abs=
if [ -n "$agent_history_file" ]; then
  agent_history_file_abs=$(abspath "$agent_history_file")
fi
agent_settings_file_abs=
if [ -n "$agent_settings_file" ]; then
  agent_settings_file_abs=$(abspath "$agent_settings_file")
fi

echo "package_root=$PACKAGE_ROOT"
echo "target_root=$target_root_abs"
echo "codex_home=$codex_home_abs"
echo "codex_bin=$codex_bin_resolved"
echo "codex_runtime_read_path=$codex_runtime_read_path"
echo "command_name=$command_name"
echo "command_path=$bin_dir_abs/$command_name"
echo "mode=$mode"
echo "backup_existing=$backup_existing"
if [ -n "$shell_rc_abs" ]; then
  echo "shell_rc=$shell_rc_abs"
else
  echo "shell_rc=(not provided)"
  if [ "$mode" = "dry-run" ]; then
    echo "note: --apply without --shell-rc requires interactive confirmation or --confirm-no-shell-rc"
  fi
fi
if [ -n "$agent_history_file_abs" ]; then
  echo "agent_history_file=$agent_history_file_abs"
fi
if [ -n "$agent_settings_file_abs" ]; then
  echo "agent_settings_file=$agent_settings_file_abs"
fi

preflight_apply_conflicts

if [ "$mode" = "apply" ] && [ -z "$shell_rc_abs" ] && [ "$confirm_no_shell_rc" != "true" ]; then
  confirm_without_shell_rc
fi

run_portable_installer
run_command_installer
record_codex_agent_settings
print_config_next_step
