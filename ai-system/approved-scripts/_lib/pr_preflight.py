#!/usr/bin/env python3
"""Non-publishing GitHub pull-request preflight for workspace repositories.

The default mode reads local Git state and GitHub metadata. ``--fetch`` is
explicit because it contacts the selected remote and updates local
remote-tracking refs and FETCH_HEAD. The helper never commits, pushes, creates
or edits a pull request, merges, or triggers workflows.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[3]
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
URI_USERINFO = re.compile(r"(?i)\b(https?://)[^/\s:@]+:[^@\s/]+@")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(token|password|passwd|secret|api[_-]?key|client[_-]?secret|"
    r"authorization|cookie|bearer)(\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
TOKEN_VALUE = re.compile(r"\b(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]{12,}\b")
BEARER_VALUE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{8,}")
PEM_BLOCK = re.compile(
    r"-----BEGIN [^-\r\n]+-----.*?-----END [^-\r\n]+-----",
    re.DOTALL,
)


class PreflightError(ValueError):
    """Raised when preflight cannot safely identify its local target."""


class CmdResult:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def detail(self) -> str:
        return (self.stderr or self.stdout).strip()


def run(cmd: list[str], cwd: Path, timeout: int = 60) -> CmdResult:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return CmdResult(127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return CmdResult(124, stdout, stderr or f"timeout after {timeout}s")
    return CmdResult(proc.returncode, proc.stdout, proc.stderr)


def strip_sensitive(text: str, limit: int = 500) -> str:
    text = ANSI_ESCAPE.sub("", text.replace("\r", ""))
    text = CONTROL.sub("", text)
    text = PEM_BLOCK.sub("<redacted-private-key>", text)
    text = URI_USERINFO.sub(r"\1<redacted>@", text)
    text = TOKEN_VALUE.sub("<redacted-token>", text)
    text = BEARER_VALUE.sub("Bearer <redacted>", text)
    text = SECRET_ASSIGNMENT.sub(lambda match: match.group(1) + match.group(2) + "<redacted>", text)
    text = text.strip()
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def one_line(text: Any, limit: int = 500) -> str:
    return strip_sensitive(str(text), limit=limit).replace("\n", "\\n").replace("`", "\\`")


def git(cwd: Path, args: list[str], timeout: int = 60) -> CmdResult:
    return run(["git", *args], cwd=cwd, timeout=timeout)


def gh(cwd: Path, args: list[str], timeout: int = 60) -> CmdResult:
    return run(["gh", *args], cwd=cwd, timeout=timeout)


def git_stdout(cwd: Path, args: list[str], default: str = "") -> str:
    result = git(cwd, args)
    return result.stdout.strip() if result.ok else default


def is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def ensure_within_workspace(path: Path, workspace: Path) -> None:
    resolved_path = path.expanduser().resolve()
    resolved_workspace = workspace.expanduser().resolve()
    if resolved_path != resolved_workspace and not is_under(resolved_path, resolved_workspace):
        raise PreflightError(f"repo path is outside the workspace root: {resolved_path}")


def find_repo_root(start: Path) -> Path:
    result = git(start, ["rev-parse", "--show-toplevel"])
    if not result.ok:
        raise PreflightError("not inside a Git repository")
    return Path(result.stdout.strip()).resolve()


def discover_templates(repo: Path) -> list[Path]:
    github_dir = repo / ".github"
    if not github_dir.is_dir():
        return []
    templates: list[Path] = []
    for path in github_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(github_dir)
        if len(rel.parts) > 3:
            continue
        if path.name.startswith("PULL_REQUEST_TEMPLATE") or any(
            part.startswith("PULL_REQUEST_TEMPLATE") for part in rel.parts[:-1]
        ):
            templates.append(path)
    return sorted(templates)


def configured_remotes(repo: Path) -> list[str]:
    return [line for line in git_stdout(repo, ["remote"]).splitlines() if line]


def select_remote(remotes: list[str], preferred: str) -> str:
    if not preferred or preferred.startswith("-") or any(char in preferred for char in "\r\n\x00"):
        raise PreflightError("remote name is invalid")
    if preferred not in remotes:
        available = ", ".join(remotes) if remotes else "none"
        raise PreflightError(
            f"requested remote is not configured: {preferred} (available: {available})"
        )
    return preferred


def repository_slug(remote_url: str) -> str:
    value = remote_url.strip()
    if "://" in value:
        parsed = urlsplit(value)
        if parsed.scheme not in {"https", "http", "ssh", "git"} or not parsed.hostname:
            raise PreflightError("selected remote is not a supported hosted Git URL")
        path = parsed.path
    else:
        match = re.fullmatch(r"(?:[^@/\s]+@)?[^:/\s]+:(.+)", value)
        if not match:
            raise PreflightError("selected remote is not a supported hosted Git URL")
        path = match.group(1)
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise PreflightError("selected remote URL does not identify owner/repository")
    owner, name = parts
    if name.endswith(".git"):
        name = name[:-4]
    safe_part = re.compile(r"[A-Za-z0-9_.-]+")
    if not owner or not name or not safe_part.fullmatch(owner) or not safe_part.fullmatch(name):
        raise PreflightError("selected remote URL contains an unsupported repository name")
    return f"{owner}/{name}"


def selected_repository(repo: Path, remote: str) -> str:
    result = git(repo, ["remote", "get-url", remote])
    if not result.ok:
        raise PreflightError(f"cannot read URL for selected remote: {remote}")
    return repository_slug(result.stdout)


def default_branch(repo: Path, repository: str, remote: str) -> tuple[str, str]:
    result = gh(
        repo,
        ["repo", "view", repository, "--json", "defaultBranchRef,nameWithOwner"],
        timeout=30,
    )
    if result.ok:
        try:
            data = json.loads(result.stdout)
            name = data.get("defaultBranchRef", {}).get("name")
            if name:
                return str(name), "gh repo view"
        except json.JSONDecodeError:
            pass

    sym = git(repo, ["symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD"])
    if sym.ok and "/" in sym.stdout.strip():
        return sym.stdout.strip().split("/", 1)[1], f"{remote}/HEAD"
    return "main", "fallback"


def resolve_ref(repo: Path, candidates: list[str]) -> tuple[str | None, str | None]:
    for candidate in candidates:
        if not candidate or any(char in candidate for char in "\r\n\x00"):
            continue
        result = git(
            repo,
            ["rev-parse", "--verify", "--end-of-options", f"{candidate}^{{commit}}"],
        )
        if result.ok:
            return candidate, result.stdout.strip()
    return None, None


def count_commits(repo: Path, base_ref: str, head_ref: str) -> tuple[int | None, list[str]]:
    result = git(repo, ["log", "--oneline", f"{base_ref}..{head_ref}"])
    if not result.ok:
        return None, [strip_sensitive(result.detail)]
    commits = [one_line(line, 240) for line in result.stdout.splitlines() if line.strip()]
    return len(commits), commits[:10]


def local_merge_check(repo: Path, base_ref: str, head_ref: str) -> tuple[str, str]:
    merge_base = git(repo, ["merge-base", head_ref, base_ref])
    if not merge_base.ok:
        return "unknown", strip_sensitive(merge_base.detail)
    tree = git(repo, ["merge-tree", merge_base.stdout.strip(), head_ref, base_ref], timeout=120)
    if not tree.ok:
        return "unknown", strip_sensitive(tree.detail)
    markers = ("<<<<<<<", "changed in both", "CONFLICT", "both modified")
    if any(marker in tree.stdout for marker in markers):
        return "conflict-risk", "local merge-tree reports conflict markers"
    return "ok", f"merge-base {merge_base.stdout.strip()[:12]}"


def diff_check(repo: Path, base_ref: str, head_ref: str) -> tuple[str, str]:
    result = git(repo, ["diff", "--check", f"{base_ref}...{head_ref}"])
    if result.ok:
        return "ok", "no whitespace errors"
    return "failed", strip_sensitive(result.detail)


def existing_pr(
    repo: Path, repository: str, head: str
) -> tuple[list[dict[str, Any]], str | None]:
    if not head or head == "HEAD":
        return [], "detached head has no branch name for gh pr list --head"
    result = gh(
        repo,
        [
            "pr",
            "list",
            "--repo",
            repository,
            "--head",
            head,
            "--state",
            "all",
            "--limit",
            "5",
            "--json",
            "number,url,state,baseRefName,headRefName,mergeable,mergeStateStatus",
        ],
        timeout=60,
    )
    if not result.ok:
        return [], strip_sensitive(result.detail)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [], f"cannot parse gh pr list JSON: {exc}"
    return data if isinstance(data, list) else [], None


def print_report(report: dict[str, Any]) -> None:
    print("# PR Preflight")
    print()
    print(f"- Repo: `{one_line(report['repo'])}`")
    print(f"- GitHub repository: `{one_line(report['repository'])}`")
    print(f"- Remote: `{one_line(report['remote'])}`")
    print(f"- Branch: `{one_line(report['branch'])}`")
    print(f"- Upstream: `{one_line(report['upstream'] or 'none')}`")
    print(f"- Base: `{one_line(report['base'])}` via {one_line(report['base_source'])}")
    print(f"- Base ref: `{one_line(report['base_ref'] or 'unresolved')}`")
    print(f"- Head ref: `{one_line(report['head_ref'] or 'unresolved')}`")
    print(f"- gh auth: {one_line(report['gh_auth'])}")
    print(f"- Fetch: {one_line(report['fetch'])}")
    print()

    print("## Templates")
    if report["templates"]:
        for template in report["templates"]:
            print(f"- `{one_line(template)}`")
    else:
        print("- none found under `.github`")
    print()

    print("## Working Tree")
    print(f"- Status: {one_line(report['worktree_status'])}")
    for line in report["status_lines"][:12]:
        print(f"  - `{one_line(line)}`")
    if len(report["status_lines"]) > 12:
        print(f"  - ... {len(report['status_lines']) - 12} more")
    print()

    print("## Commits")
    if report["ahead_count"] is None:
        print("- ahead count unknown")
    else:
        print(
            f"- `{one_line(report['head_ref'])}` ahead "
            f"`{one_line(report['base_ref'])}`: {report['ahead_count']} commits"
        )
        for line in report["ahead_preview"]:
            print(f"  - `{one_line(line)}`")
    print()

    print("## Merge / Diff")
    print(
        f"- Local merge-tree: {one_line(report['local_merge_state'])} "
        f"({one_line(report['local_merge_detail'])})"
    )
    print(f"- Diff check: {one_line(report['diff_check'])} ({one_line(report['diff_detail'])})")
    print()

    print("## Existing PR")
    if report["existing_pr_error"]:
        print(f"- gh lookup warning: {one_line(report['existing_pr_error'])}")
    if report["existing_prs"]:
        for pr in report["existing_prs"]:
            print(
                "- "
                f"#{one_line(pr.get('number'))} `{one_line(pr.get('state'))}` "
                f"`{one_line(pr.get('baseRefName'))} <- {one_line(pr.get('headRefName'))}` "
                f"mergeable={one_line(pr.get('mergeable'))} "
                f"mergeStateStatus={one_line(pr.get('mergeStateStatus'))} "
                f"{one_line(pr.get('url'))}"
            )
    else:
        print("- none found for current head")
    print()

    print("## Required Manual Gate")
    print("- Confirm remote / base / head / upstream.")
    print("- Confirm PR title and body draft before creating a PR.")
    print("- If a template exists, preserve its headings, checkboxes, and code blocks.")
    if report["blockers"]:
        print()
        print("## Blockers / Warnings")
        for blocker in report["blockers"]:
            print(f"- {one_line(blocker)}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run non-publishing GitHub PR preflight checks.")
    parser.add_argument("--repo", default=".", help="repo/worktree path; default: cwd")
    parser.add_argument("--remote", default="origin", help="exact configured remote; default: origin")
    parser.add_argument("--base", help="base branch name; default: GitHub default or remote HEAD")
    parser.add_argument("--head", help="head branch/ref; default: current branch or HEAD")
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="contact the selected remote and update local remote-tracking refs",
    )
    parser.add_argument("--strict", action="store_true", help="return non-zero when blockers exist")
    args = parser.parse_args(argv)

    workspace = ROOT.resolve()
    start = Path(args.repo).expanduser()
    if not start.is_absolute():
        start = workspace / start
    start = start.resolve()

    try:
        ensure_within_workspace(start, workspace)
        repo = find_repo_root(start)
        ensure_within_workspace(repo, workspace)
        remote = select_remote(configured_remotes(repo), args.remote)
        repository = selected_repository(repo, remote)
    except PreflightError as exc:
        print(f"pr-preflight: {exc}", file=sys.stderr)
        return 2

    branch = git_stdout(repo, ["branch", "--show-current"]) or "DETACHED"
    head = args.head or (branch if branch != "DETACHED" else "HEAD")
    upstream = git_stdout(repo, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])

    fetch_state = "skipped (use --fetch to update local remote-tracking refs)"
    blockers: list[str] = []
    if args.fetch:
        fetched = git(repo, ["fetch", remote], timeout=180)
        if fetched.ok:
            fetch_state = f"ok ({remote})"
        else:
            fetch_state = f"failed ({strip_sensitive(fetched.detail)})"
            blockers.append("remote refs may be stale because git fetch failed")

    base, base_source = (
        (args.base, "argument")
        if args.base
        else default_branch(repo, repository, remote)
    )
    base_ref, base_sha = resolve_ref(repo, [f"{remote}/{base}", base])
    head_candidates = [head, f"{remote}/{head}"]
    if args.head is None:
        head_candidates.append("HEAD")
    head_ref, head_sha = resolve_ref(repo, head_candidates)
    if base_ref is None:
        blockers.append(f"cannot resolve base branch: {base}")
    if head_ref is None:
        blockers.append(f"cannot resolve head ref: {head}")

    gh_auth_result = gh(repo, ["auth", "status"], timeout=30)
    gh_auth = "ok" if gh_auth_result.ok else f"failed ({strip_sensitive(gh_auth_result.detail, 180)})"

    templates = [str(path.relative_to(repo)) for path in discover_templates(repo)]
    status = git_stdout(repo, ["status", "--short"])
    status_lines = [line for line in status.splitlines() if line.strip()]
    worktree_status = "clean" if not status_lines else f"{len(status_lines)} changed/untracked entries"

    ahead_count: int | None = None
    ahead_preview: list[str] = []
    local_merge_state = "unknown"
    local_merge_detail = "base/head unresolved"
    diff_state = "unknown"
    diff_detail = "base/head unresolved"
    if base_sha and head_sha:
        ahead_count, ahead_preview = count_commits(repo, base_sha, head_sha)
        local_merge_state, local_merge_detail = local_merge_check(repo, base_sha, head_sha)
        diff_state, diff_detail = diff_check(repo, base_sha, head_sha)
        if local_merge_state != "ok":
            blockers.append("local merge-tree did not prove a clean merge")
        if diff_state != "ok":
            blockers.append("git diff --check failed")

    prs, pr_error = existing_pr(repo, repository, head if head != "HEAD" else branch)
    report = {
        "repo": str(repo),
        "repository": repository,
        "remote": remote,
        "branch": branch,
        "upstream": upstream,
        "base": base,
        "base_source": base_source,
        "base_ref": base_ref,
        "base_sha": base_sha,
        "head_ref": head_ref,
        "head_sha": head_sha,
        "fetch": fetch_state,
        "gh_auth": gh_auth,
        "templates": templates,
        "worktree_status": worktree_status,
        "status_lines": status_lines,
        "ahead_count": ahead_count,
        "ahead_preview": ahead_preview,
        "local_merge_state": local_merge_state,
        "local_merge_detail": local_merge_detail,
        "diff_check": diff_state,
        "diff_detail": diff_detail,
        "existing_prs": prs,
        "existing_pr_error": pr_error,
        "blockers": blockers,
    }
    print_report(report)
    return 1 if args.strict and blockers else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
