#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def default_workspace(pack_dir: Path) -> Path:
    for candidate in pack_dir.parents:
        if (candidate / "ai-system" / "approved-scripts" / "allow").is_dir():
            return candidate
    return Path.cwd()


def hook_decision(hook: Path, workspace: Path, command: str) -> str:
    trusted_dir = workspace / "ai-system" / "approved-scripts" / "allow"
    payload = {
        "hook_event_name": "PermissionRequest",
        "tool_name": "Bash",
        "cwd": str(workspace),
        "tool_input": {
            "command": command,
        },
    }
    env = os.environ.copy()
    env["TRUSTED_SCRIPT_DIR"] = str(trusted_dir)
    env["EXPECTED_CWD"] = str(workspace)

    result = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"hook exited {result.returncode}: {result.stderr.strip()}")

    stdout = result.stdout.strip()
    if not stdout:
        return "no_decision"

    data = json.loads(stdout)
    behavior = (
        data.get("hookSpecificOutput", {})
        .get("decision", {})
        .get("behavior")
    )
    return behavior or "no_decision"


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    pack_dir = script_dir.parent
    parser = argparse.ArgumentParser(description="Probe Codex trusted-script hook decisions.")
    parser.add_argument("--workspace", default=str(default_workspace(pack_dir)))
    args = parser.parse_args()

    workspace = Path(args.workspace).expanduser().resolve()
    hook = pack_dir / "hooks" / "allow_trusted_script_permission.py"
    trusted_helper = "ai-system/approved-scripts/allow/patchlog-append"

    cases = [
        ("direct trusted helper", f"{trusted_helper} --help", "allow"),
        ("bash trusted helper", f"bash {trusted_helper} --help", "allow"),
        ("python trusted helper", f"python3 {trusted_helper} --help", "allow"),
        ("env assignment", f"FOO=bar {trusted_helper} --help", "no_decision"),
        ("shell expansion", f"TOKEN=$TOKEN {trusted_helper} --help", "no_decision"),
        ("command composition", f"{trusted_helper} --help; true", "no_decision"),
        ("pipeline composition", f"{trusted_helper} --help | cat", "no_decision"),
        ("bash option", f"bash --noprofile {trusted_helper} --help", "no_decision"),
        ("python option", f"python3 -I {trusted_helper} --help", "no_decision"),
        ("node preload option", f"node --require=/tmp/preload.js {trusted_helper} --help", "no_decision"),
        ("ruby preload option", f"ruby -r/tmp/preload {trusted_helper} --help", "no_decision"),
        ("perl preload option", f"perl -Mlib=/tmp {trusted_helper} --help", "no_decision"),
        ("outside trusted dir", "bash README.md", "no_decision"),
    ]

    failures = []
    for name, command, expected in cases:
        actual = hook_decision(hook, workspace, command)
        if actual != expected:
            failures.append((name, expected, actual))
        else:
            print(f"ok: {name}")

    if failures:
        for name, expected, actual in failures:
            print(f"fail: {name}: expected {expected}, got {actual}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
