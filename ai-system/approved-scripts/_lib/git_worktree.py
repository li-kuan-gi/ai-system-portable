#!/usr/bin/env python3
"""Controlled git worktree helpers for agents."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKTREES = ROOT / ".worktrees"
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class WorktreeError(Exception):
    pass


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 2


def run_git(args: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise WorktreeError(detail or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def safe_component(value: str, field: str) -> str:
    cleaned = value.strip()
    if not SAFE_COMPONENT.fullmatch(cleaned):
        raise WorktreeError(
            f"{field} must match {SAFE_COMPONENT.pattern}; use a short task/slot slug"
        )
    return cleaned


def repo_top(repo: str) -> Path:
    raw = Path(repo).expanduser()
    if not raw.is_absolute():
        raw = Path.cwd() / raw
    resolved = raw.resolve()
    top = Path(run_git(["rev-parse", "--show-toplevel"], cwd=resolved)).resolve()
    try:
        top.relative_to(ROOT)
    except ValueError as exc:
        raise WorktreeError("repo must be inside the workspace root") from exc
    return top


def repo_slug(repo: Path) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", repo.name).strip(".-_")
    if not slug:
        raise WorktreeError("repo name cannot be converted to a safe path component")
    return slug[:64]


def worktree_path(repo: Path, task: str, slot: str) -> Path:
    task_slug = safe_component(task, "task")
    slot_slug = safe_component(slot, "slot")
    path = WORKTREES / task_slug / repo_slug(repo) / slot_slug
    resolved = path.resolve()
    try:
        resolved.relative_to(WORKTREES.resolve())
    except ValueError as exc:
        raise WorktreeError("worktree path escaped the managed directory") from exc
    if resolved.exists() or resolved.is_symlink():
        raise WorktreeError(f"worktree path already exists: {resolved}")
    return resolved


def ensure_ref(ref: str) -> str:
    cleaned = ref.strip()
    if not cleaned or "\x00" in cleaned:
        raise WorktreeError("ref is required")
    return cleaned


def add_detached(args: argparse.Namespace) -> None:
    repo = repo_top(args.repo)
    ref = ensure_ref(args.ref)
    path = worktree_path(repo, args.task, args.slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    run_git(["worktree", "add", "--detach", str(path), ref], cwd=repo)
    print(f"worktree={path}")
    print("mode=detached")
    print(f"ref={ref}")


def add_branch(args: argparse.Namespace) -> None:
    repo = repo_top(args.repo)
    ref = ensure_ref(args.start_ref)
    task = safe_component(args.task, "task")
    slot = safe_component(args.slot, "slot")
    branch = args.branch.strip() if args.branch else f"agent/{task}/{slot}"
    if not branch:
        raise WorktreeError("branch name cannot be empty")
    run_git(["check-ref-format", "--branch", branch], cwd=repo)
    path = worktree_path(repo, task, slot)
    path.parent.mkdir(parents=True, exist_ok=True)
    run_git(["worktree", "add", "-b", branch, str(path), ref], cwd=repo)
    print(f"worktree={path}")
    print("mode=branch")
    print(f"branch={branch}")
    print(f"start_ref={ref}")


def remove_clean(args: argparse.Namespace) -> None:
    raw = Path(args.worktree).expanduser()
    if not raw.is_absolute():
        raw = Path.cwd() / raw
    target = raw.resolve()
    try:
        target.relative_to(WORKTREES.resolve())
    except ValueError as exc:
        raise WorktreeError("worktree must be under the managed .worktrees directory") from exc
    if target == WORKTREES.resolve():
        raise WorktreeError("refusing to remove the managed .worktrees root")
    if raw.is_symlink() or not target.is_dir():
        raise WorktreeError("worktree must be an existing directory, not a symlink")
    top = Path(run_git(["rev-parse", "--show-toplevel"], cwd=target)).resolve()
    if top != target:
        raise WorktreeError(f"path is not a worktree root; root is {top}")
    status = run_git(["status", "--porcelain", "--untracked-files=all"], cwd=target)
    if status:
        raise WorktreeError("worktree is not clean; inspect changes before removal")
    common = Path(run_git(["rev-parse", "--git-common-dir"], cwd=target))
    if not common.is_absolute():
        common = (target / common).resolve()
    run_git([f"--git-dir={common}", "worktree", "remove", str(target)])
    parent = target.parent
    while parent != WORKTREES and parent != ROOT:
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent
    print(f"removed={target}")


def pull_clean(args: argparse.Namespace) -> None:
    repo = repo_top(args.repo)
    status = run_git(["status", "--porcelain", "--untracked-files=all"], cwd=repo)
    if status:
        raise WorktreeError("working tree is not clean; use git fetch or an isolated worktree")
    run_git(["pull", "--ff-only"], cwd=repo)
    print(f"pulled={repo}")
    print("mode=ff-only")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Controlled git worktree helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p_detached = sub.add_parser("add-detached")
    p_detached.add_argument("repo")
    p_detached.add_argument("task")
    p_detached.add_argument("slot")
    p_detached.add_argument("ref")
    p_detached.set_defaults(func=add_detached)

    p_branch = sub.add_parser("add-branch")
    p_branch.add_argument("repo")
    p_branch.add_argument("task")
    p_branch.add_argument("slot")
    p_branch.add_argument("start_ref")
    p_branch.add_argument(
        "--branch",
        default=None,
        help="branch name to create (default: agent/<task>/<slot>)",
    )
    p_branch.set_defaults(func=add_branch)

    p_remove = sub.add_parser("remove-clean")
    p_remove.add_argument("worktree")
    p_remove.set_defaults(func=remove_clean)

    p_pull = sub.add_parser("pull-clean")
    p_pull.add_argument("repo")
    p_pull.set_defaults(func=pull_clean)

    return parser


def main(argv: list[str]) -> int:
    try:
        args = build_parser().parse_args(argv)
        args.func(args)
        return 0
    except WorktreeError as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
