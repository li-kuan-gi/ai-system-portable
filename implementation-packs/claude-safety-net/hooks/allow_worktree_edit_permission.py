#!/usr/bin/env python3
"""Claude Code PreToolUse hook：放行 .worktrees/ 內的檔案編輯（safety-net.md §1 / §2.1）。

`Edit/Write/NotebookEdit(.worktrees/**)` 這種靜態 glob 無法乾淨地涵蓋路徑中含
`.` 開頭片段的隱藏檔 / 隱藏目錄（gitignore 式 `**` 預設跳過 dotfile）。本 hook 改用
「目標絕對路徑是否落在 <workspace>/.worktrees/ 底下」來判斷，因此 dot 路徑也一定吃得到。

機械式決策（其他一律 no_decision，回到 Claude 正常 ask 流程）：
- allow：Edit / Write / MultiEdit / NotebookEdit 的目標路徑解析後落在 .worktrees/ 內。

安全性：
- 目標路徑先 resolve()（正規化 `..`、跟隨 symlink）再比對 —— 任何指向 .worktrees/
  外面的 symlink 或 `../` 逃逸都會解析到外部 → is_under 為 False → no_decision（ask），
  絕不會誤放行。
- 路徑無法判定（缺 EXPECTED_CWD / 無 file_path）一律 no_decision。

I/O 採 Claude Code PreToolUse hook 協定：
- stdin: {"hook_event_name":"PreToolUse","tool_name":"Edit","cwd":"...",
    "tool_input":{"file_path":"..."}}
- stdout(allow): {"hookSpecificOutput":{"hookEventName":"PreToolUse",
    "permissionDecision":"allow","permissionDecisionReason":"..."}}
- stdout(no decision): 不輸出 JSON
"""
import json
import os
import sys
from pathlib import Path


EXPECTED_CWD_RAW = os.environ.get("EXPECTED_CWD")
EXPECTED_CWD = Path(EXPECTED_CWD_RAW).expanduser().resolve() if EXPECTED_CWD_RAW else None
WORKTREES_DIR = (EXPECTED_CWD / ".worktrees").resolve() if EXPECTED_CWD is not None else None

# Edit / Write / MultiEdit 用 file_path；NotebookEdit 用 notebook_path。
FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PATH_KEYS = ("file_path", "notebook_path")


def no_decision() -> int:
    return 0


def emit(decision: str, reason: str) -> int:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    return 0


def is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def target_path(tool_input: dict, cwd: Path) -> Path | None:
    for key in PATH_KEYS:
        raw = tool_input.get(key)
        if isinstance(raw, str) and raw.strip():
            p = Path(raw).expanduser()
            if not p.is_absolute():
                p = cwd / p
            return p.resolve()
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return no_decision()

    if payload.get("hook_event_name") != "PreToolUse":
        return no_decision()
    if payload.get("tool_name") not in FILE_TOOLS:
        return no_decision()
    if WORKTREES_DIR is None:
        return no_decision()

    cwd = Path(payload.get("cwd") or ".").expanduser().resolve()
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return no_decision()

    target = target_path(tool_input, cwd)
    if target is None:
        return no_decision()

    if is_under(target, WORKTREES_DIR):
        return emit("allow", ".worktrees/ 內檔案編輯（safety-net.md §1 / §2.1）。")

    return no_decision()


if __name__ == "__main__":
    raise SystemExit(main())
