#!/usr/bin/env python3
"""Validate and run a narrow Maven wrapper verification command.

This helper is an accidental-operation guard, not a code sandbox. A repository
controls its Maven wrapper, POM, extensions, plugins, and tests; those may run
code, use the network, read Maven settings, and update the normal local cache.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKTREES = ROOT / ".worktrees"

ALLOWED_GOALS = {
    "clean",
    "compile",
    "validate",
    "test-compile",
    "test",
    "package",
    "spotless:check",
}

VERSION_GOALS = {"-v", "--version", "-version"}

FLAG_OPTIONS = {
    "-B",
    "--batch-mode",
    "-e",
    "--errors",
    "-q",
    "--quiet",
    "-X",
    "--debug",
    "-o",
    "--offline",
    "-N",
    "--non-recursive",
    "-U",
    "--update-snapshots",
    "-nsu",
    "--no-snapshot-updates",
    "-ntp",
    "--no-transfer-progress",
    "-V",
    "--show-version",
    "-C",
    "--strict-checksums",
    "-c",
    "--lax-checksums",
    "-fae",
    "--fail-at-end",
    "-ff",
    "--fail-fast",
    "-am",
    "--also-make",
    "-amd",
    "--also-make-dependents",
}

VALUE_OPTIONS = {
    "-pl": "--projects",
    "-rf": "--resume-from",
    "-P": "--activate-profiles",
    "-T": "--threads",
}

FORBIDDEN_GOAL_FRAGMENTS = (
    "deploy",
    "release:",
    "jib:",
    "docker",
    "spring-boot:run",
    "spring-boot:start",
    "spring-boot:stop",
    "spring-boot:build-image",
    "exec:",
    "fabric8:",
    "helm:",
    "k8s:",
)

SECRET_PROPERTY = re.compile(
    r"(?i)(token|password|passwd|secret|bearer|cookie|authorization|apikey|api-key)"
)

FORBIDDEN_PROPERTIES = {
    "maven.repo.local",
    "altdeploymentrepository",
    "altreleasedeploymentrepository",
    "altsnapshotdeploymentrepository",
}


class ValidationError(ValueError):
    """Raised when a requested Maven invocation crosses the helper boundary."""


def is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_repo(raw: str) -> Path:
    repo = Path(raw).expanduser()
    if not repo.is_absolute():
        repo = ROOT / repo
    repo = repo.resolve()
    worktrees = WORKTREES.resolve()
    if repo == worktrees or not is_under(repo, worktrees):
        raise ValidationError("mvnw-check only runs inside .worktrees/ repo checkouts")
    if not repo.is_dir():
        raise ValidationError(f"repo is not a directory: {repo}")

    root_result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if root_result.returncode != 0:
        raise ValidationError(f"not a Git checkout: {repo}")
    if Path(root_result.stdout.strip()).resolve() != repo:
        raise ValidationError("--repo must name the checkout root, not a nested directory")

    mvnw = repo / "mvnw"
    if mvnw.is_symlink():
        raise ValidationError(f"Maven wrapper must not be a symlink: {mvnw}")
    if not mvnw.is_file():
        raise ValidationError(f"missing Maven wrapper: {mvnw}")
    if not os.access(mvnw, os.X_OK):
        raise ValidationError(f"Maven wrapper is not executable: {mvnw}")
    return repo


def property_name(arg: str) -> str | None:
    if not arg.startswith("-D") or len(arg) <= 2:
        return None
    name = arg[2:].split("=", 1)[0].strip().lower()
    return name or None


def reject_property(arg: str) -> str | None:
    name = property_name(arg)
    if name is None:
        return "-D must include a property name"
    if name in FORBIDDEN_PROPERTIES:
        return f"property is not allowed in mvnw-check: {name}"
    if name.startswith(("jib.", "docker.", "maven.deploy.", "spring-boot.run.")):
        return f"high-risk property is not allowed in mvnw-check: {name}"
    if SECRET_PROPERTY.search(name):
        return f"secret-like property is not allowed in mvnw-check: {name}"
    return None


def validate_environment(env: Mapping[str, str]) -> None:
    if env.get("MAVEN_ARGS", "").strip():
        raise ValidationError(
            "MAVEN_ARGS must be unset because it can add unvalidated Maven goals or options"
        )


def _validate_option_value(option: str, value: str) -> None:
    if not value or any(char in value for char in ("\x00", "\n", "\r")):
        raise ValidationError(f"invalid value for Maven option: {option}")


def validate_args(args: list[str]) -> list[str]:
    if not args:
        raise ValidationError("mvnw-check requires Maven arguments after --")
    if all(arg in VERSION_GOALS for arg in args):
        return []
    if any(arg in VERSION_GOALS for arg in args):
        raise ValidationError("Maven version options cannot be combined with verification goals")

    goals: list[str] = []
    long_value_options = set(VALUE_OPTIONS.values())
    i = 0
    while i < len(args):
        arg = args[i]
        lower = arg.lower()

        if any(fragment in lower for fragment in FORBIDDEN_GOAL_FRAGMENTS):
            raise ValidationError(f"high-risk Maven operation is not allowed: {arg}")

        if arg.startswith("-D"):
            prop_error = reject_property(arg)
            if prop_error:
                raise ValidationError(prop_error)
            i += 1
            continue

        if arg in FLAG_OPTIONS:
            i += 1
            continue

        if arg in VALUE_OPTIONS or arg in long_value_options:
            if i + 1 >= len(args):
                raise ValidationError(f"missing value for Maven option: {arg}")
            _validate_option_value(arg, args[i + 1])
            i += 2
            continue

        matched_value_option = False
        for short, long in VALUE_OPTIONS.items():
            if arg.startswith(short) and len(arg) > len(short):
                _validate_option_value(short, arg[len(short) :])
                matched_value_option = True
                break
            prefix = long + "="
            if arg.startswith(prefix):
                _validate_option_value(long, arg[len(prefix) :])
                matched_value_option = True
                break
        if matched_value_option:
            i += 1
            continue

        if arg.startswith("-"):
            raise ValidationError(f"Maven option is not allowlisted: {arg}")

        if arg not in ALLOWED_GOALS:
            raise ValidationError(f"Maven goal is not allowed in mvnw-check: {arg}")
        goals.append(arg)
        i += 1

    if not goals:
        raise ValidationError("mvnw-check requires at least one allowed Maven goal")
    return goals


def display_args(args: list[str]) -> list[str]:
    shown: list[str] = []
    for arg in args:
        if arg.startswith("-D") and "=" in arg:
            shown.append(arg.split("=", 1)[0] + "=<redacted>")
        else:
            shown.append(arg)
    return shown


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Run a narrow Maven wrapper verification command in a managed worktree."
    )
    parser.add_argument("--repo", required=True, help="repo checkout under .worktrees/")
    parser.add_argument("--dry-run", action="store_true", help="print impact without running Maven")
    parser.add_argument("maven_args", nargs=argparse.REMAINDER, help="Maven arguments after --")
    ns = parser.parse_args(argv)

    maven_args = list(ns.maven_args)
    if maven_args and maven_args[0] == "--":
        maven_args = maven_args[1:]

    try:
        repo = resolve_repo(ns.repo)
        validate_environment(os.environ)
        validate_args(maven_args)
    except ValidationError as exc:
        print(f"mvnw-check: {exc}", file=sys.stderr)
        return 2

    command = [str(repo / "mvnw"), *maven_args]
    if ns.dry_run:
        shown = [str(repo / "mvnw"), *display_args(maven_args)]
        print(f"cwd: {repo}")
        print("impact: executes repository-controlled Maven wrapper, plugins, and tests")
        print("maven-local-repo: default (may read settings and update dependency cache)")
        print("command: " + shlex.join(shown))
        return 0

    return subprocess.run(command, cwd=str(repo), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
