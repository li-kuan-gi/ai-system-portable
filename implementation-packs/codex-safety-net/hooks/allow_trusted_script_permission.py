#!/usr/bin/env python3
import json
import os
import re
import shlex
import sys
from pathlib import Path


TRUSTED_SCRIPT_DIR = Path(os.environ["TRUSTED_SCRIPT_DIR"]).expanduser().resolve()
EXPECTED_CWD_RAW = os.environ.get("EXPECTED_CWD")
EXPECTED_CWD = Path(EXPECTED_CWD_RAW).expanduser().resolve() if EXPECTED_CWD_RAW else None

# 只自動核准「單純執行一個腳本」。
# 允許 shell line-continuation 寫成多行參數；其他換行與 ; && | > < ` $(...)
# 等 shell 組合語法不自動核准，回到手動 approval。
LINE_CONTINUATION = re.compile(r"\\\r?\n[ \t]*")
CONTROL_OPERATORS = set(";&|<>")

ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")

INTERPRETERS = {
    "bash",
    "sh",
    "zsh",
    "python",
    "python3",
}


def no_decision() -> int:
    # stdout 不輸出任何 JSON = 讓 Codex 照正常 approval 流程處理
    return 0


def approve() -> int:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {
                "behavior": "allow"
            }
        }
    }))
    return 0


def is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_token_as_path(token: str, cwd: Path) -> Path:
    p = Path(token).expanduser()
    if not p.is_absolute():
        p = cwd / p
    return p.resolve()


def normalize_command(command: str) -> str:
    # Shell 會在 parsing 前移除 backslash-newline；hook 要用同樣視角判斷。
    return LINE_CONTINUATION.sub(" ", command)


def has_unsafe_shell_syntax(command: str) -> bool:
    in_single = False
    in_double = False
    escaped = False
    i = 0

    while i < len(command):
        ch = command[i]

        if ch == "\n":
            return True

        if escaped:
            escaped = False
            i += 1
            continue

        if ch == "\\" and not in_single:
            escaped = True
            i += 1
            continue

        if ch == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue

        if ch == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue

        # Backticks and command substitution are active outside single quotes,
        # including inside double quotes, so keep them out of auto-approval.
        if not in_single and ch == "`":
            return True

        # Any unquoted shell expansion is outside the trusted-script subset.
        # This includes $VAR, ${VAR}, $1, $? and command substitution.
        if not in_single and ch == "$":
            return True

        # Shell control operators only matter outside quotes. Quoted '&' in a
        # URL query string is a normal argument and should not block approval.
        if not in_single and not in_double and ch in CONTROL_OPERATORS:
            return True

        i += 1

    return False


def find_script_path(tokens: list[str], cwd: Path) -> Path | None:
    """
    支援兩種形式：

      /abs/workspace/approved-scripts/foo.sh arg1
      ./approved-scripts/foo.sh arg1

      bash /abs/workspace/approved-scripts/foo.sh arg1
      python3 ./approved-scripts/foo.py arg1

    不支援：
      bash --noprofile ./approved-scripts/foo.sh
      python3 -I ./approved-scripts/foo.py
      bash -c '...'
      sh -c '...'
      node --require=/tmp/preload.js ./approved-scripts/foo.js
      ruby -r/tmp/preload ./approved-scripts/foo.rb
      perl -Mlib=/tmp ./approved-scripts/foo.pl
      cmd1 && cmd2
      cmd1 | cmd2
      cd somewhere && script.sh
    """
    i = 0

    # Env assignment changes execution semantics and may smuggle local values
    # through shell expansion. Do not auto-approve it.
    if i < len(tokens) and ENV_ASSIGNMENT.match(tokens[i]):
        return None

    if i >= len(tokens):
        return None

    exe = tokens[i]
    exe_name = Path(exe).name

    # 直接執行腳本：/path/script.sh 或 ./script.sh 或 dir/script.sh
    if "/" in exe or exe.startswith("."):
        return resolve_token_as_path(exe, cwd)

    # 透過 interpreter 執行：bash script.sh / python3 script.py
    if exe_name in INTERPRETERS:
        j = i + 1

        # Interpreter option 會改變 runtime 載入面或 execution mode。
        # trusted-script auto-allow 只涵蓋無 option 的 script execution。
        if j < len(tokens) and tokens[j].startswith("-"):
            return None

        if j < len(tokens):
            return resolve_token_as_path(tokens[j], cwd)

    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return no_decision()

    if payload.get("hook_event_name") != "PermissionRequest":
        return no_decision()

    if payload.get("tool_name") != "Bash":
        return no_decision()

    cwd = Path(payload.get("cwd") or ".").expanduser().resolve()

    # 你說 Codex 都從固定目錄啟動，所以這裡加一層保護。
    # 如果 cwd 不是固定目錄，就不自動核准。
    if EXPECTED_CWD is not None and cwd != EXPECTED_CWD:
        return no_decision()

    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") or ""

    if not isinstance(command, str) or not command.strip():
        return no_decision()

    command = normalize_command(command)

    if has_unsafe_shell_syntax(command):
        return no_decision()

    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return no_decision()

    script_path = find_script_path(tokens, cwd)
    if script_path is None:
        return no_decision()

    if not script_path.exists() or not script_path.is_file():
        return no_decision()

    if is_under(script_path, TRUSTED_SCRIPT_DIR):
        return approve()

    return no_decision()


if __name__ == "__main__":
    raise SystemExit(main())
