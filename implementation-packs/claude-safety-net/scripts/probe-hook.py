#!/usr/bin/env python3
"""Generic regression probe for the Claude Code safety-net hooks.

Runs a small set of service-neutral cases against the installed pack hooks and
checks each decision. No workspace-specific commands or paths are hard-coded.

Usage (from the portable package root, or pass --workspace):
    python3 implementation-packs/claude-safety-net/scripts/probe-hook.py
    python3 implementation-packs/claude-safety-net/scripts/probe-hook.py --workspace /path/to/workspace

Exit code 0 when every case matches the expected decision, 1 otherwise.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def decide(hook: Path, payload: dict, env: dict) -> str:
    r = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    out = r.stdout.strip()
    if not out:
        return "no_decision"
    try:
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"]
    except Exception:
        return f"bad_output:{out!r}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default=os.getcwd())
    args = parser.parse_args()

    pack_dir = Path(__file__).resolve().parent.parent
    trusted_hook = pack_dir / "hooks" / "allow_trusted_script_permission.py"
    worktree_hook = pack_dir / "hooks" / "allow_worktree_edit_permission.py"

    # Use an isolated temp workspace so the probe never depends on real repos.
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp).resolve()
        allow_dir = ws / "ai-system" / "approved-scripts" / "allow"
        allow_dir.mkdir(parents=True)
        helper = allow_dir / "demo-helper"
        helper.write_text("#!/usr/bin/env sh\necho ok\n")
        helper.chmod(0o755)
        worktree_file = ws / ".worktrees" / "task" / "repo" / "slot" / "x.txt"
        worktree_file.parent.mkdir(parents=True)

        env = dict(os.environ)
        env["TRUSTED_SCRIPT_DIR"] = str(allow_dir)
        env["EXPECTED_CWD"] = str(ws)

        def bash(command: str) -> dict:
            return {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                    "cwd": str(ws), "tool_input": {"command": command}}

        def edit(path: str, tool: str = "Write") -> dict:
            return {"hook_event_name": "PreToolUse", "tool_name": tool,
                    "cwd": str(ws), "tool_input": {"file_path": path}}

        cases = [
            ("trusted script bare", trusted_hook, bash(str(helper)), "allow"),
            ("trusted via interpreter", trusted_hook, bash(f"sh {helper}"), "allow"),
            ("trusted + safe pipe", trusted_hook, bash(f"{helper} | head -5"), "allow"),
            ("read-only git", trusted_hook, bash("git log --oneline -5"), "allow"),
            ("background &", trusted_hook, bash(f"{helper} &"), "deny"),
            ("nohup detached", trusted_hook, bash(f"nohup {helper}"), "deny"),
            ("network git push -> ask", trusted_hook, bash("git push origin main"), "no_decision"),
            ("trusted + command substitution -> ask", trusted_hook, bash(f"{helper} $(whoami)"), "no_decision"),
            ("worktree edit", worktree_hook, edit(str(worktree_file)), "allow"),
            ("worktree notebook", worktree_hook, edit(str(worktree_file), "NotebookEdit"), "allow"),
            ("edit outside worktree", worktree_hook, edit(str(ws / "ai-system" / "rules.md")), "no_decision"),
        ]

        failures = 0
        for name, hook, payload, expected in cases:
            got = decide(hook, payload, env)
            ok = got == expected
            print(f"[{'PASS' if ok else 'FAIL'}] {name}: expected={expected} got={got}")
            if not ok:
                failures += 1

        print(f"\n{len(cases) - failures}/{len(cases)} passed")
        return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
