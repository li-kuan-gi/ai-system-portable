#!/usr/bin/env python3
"""Regression probes for portable approved helper boundaries."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = PACKAGE_ROOT / "ai-system" / "approved-scripts" / "_lib"
sys.path.insert(0, str(LIB_DIR))

import chat_history  # noqa: E402
import mvnw_check  # noqa: E402
import pr_preflight  # noqa: E402


class MavenCheckTests(unittest.TestCase):
    def test_dry_run_accepts_managed_git_worktree_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            repo = workspace / ".worktrees" / "task" / "project" / "slot"
            repo.mkdir(parents=True)
            subprocess.run(
                ["git", "init", "--quiet", str(repo)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            wrapper = repo / "mvnw"
            wrapper.write_text("#!/usr/bin/env sh\nexit 0\n", encoding="utf-8")
            wrapper.chmod(0o755)
            output = io.StringIO()
            with (
                mock.patch.object(mvnw_check, "ROOT", workspace),
                mock.patch.object(mvnw_check, "WORKTREES", workspace / ".worktrees"),
                mock.patch.dict(os.environ, {"MAVEN_ARGS": ""}),
                contextlib.redirect_stdout(output),
            ):
                result = mvnw_check.main(
                    ["--repo", str(repo), "--dry-run", "--", "test", "-Dfeature.flag=enabled"]
                )
            self.assertEqual(result, 0)
            self.assertIn("-Dfeature.flag=<redacted>", output.getvalue())
            self.assertNotIn("=enabled", output.getvalue())

    def test_accepts_normal_verification_goals(self) -> None:
        self.assertEqual(mvnw_check.validate_args(["test"]), ["test"])
        self.assertEqual(mvnw_check.validate_args(["package"]), ["package"])

    def test_rejects_unknown_output_option(self) -> None:
        with self.assertRaises(mvnw_check.ValidationError):
            mvnw_check.validate_args(["test", "--log-file=/tmp/maven.log"])

    def test_rejects_high_risk_goal_and_property(self) -> None:
        with self.assertRaises(mvnw_check.ValidationError):
            mvnw_check.validate_args(["deploy"])
        with self.assertRaises(mvnw_check.ValidationError):
            mvnw_check.validate_args(["test", "-DapiToken=example-value"])

    def test_rejects_maven_args_environment_bypass(self) -> None:
        with self.assertRaises(mvnw_check.ValidationError):
            mvnw_check.validate_environment({"MAVEN_ARGS": "deploy"})

    def test_dry_run_redacts_property_values(self) -> None:
        self.assertEqual(
            mvnw_check.display_args(["test", "-Dfeature.flag=enabled"]),
            ["test", "-Dfeature.flag=<redacted>"],
        )


class PrPreflightTests(unittest.TestCase):
    def test_default_branch_uses_repo_view_positional_target(self) -> None:
        response = pr_preflight.CmdResult(
            0,
            json.dumps({"defaultBranchRef": {"name": "main"}}),
            "",
        )
        repo = Path("/tmp/example-repo")
        with mock.patch.object(pr_preflight, "gh", return_value=response) as gh_call:
            branch, source = pr_preflight.default_branch(repo, "example/project", "origin")
        self.assertEqual((branch, source), ("main", "gh repo view"))
        gh_call.assert_called_once_with(
            repo,
            ["repo", "view", "example/project", "--json", "defaultBranchRef,nameWithOwner"],
            timeout=30,
        )

    def test_github_target_is_derived_from_selected_remote_url(self) -> None:
        self.assertEqual(
            pr_preflight.repository_slug("git@github-alias:example/project.git"),
            "example/project",
        )
        self.assertEqual(
            pr_preflight.repository_slug("https://github.com/example/project.git"),
            "example/project",
        )
        with self.assertRaises(pr_preflight.PreflightError):
            pr_preflight.repository_slug("/tmp/local-repo")

    def test_existing_pr_query_omits_ci_status_fields(self) -> None:
        response = pr_preflight.CmdResult(0, "[]", "")
        repo = Path("/tmp/example-repo")
        with mock.patch.object(pr_preflight, "gh", return_value=response) as gh_call:
            pull_requests, error = pr_preflight.existing_pr(
                repo,
                "example/project",
                "feature/example",
            )
        self.assertEqual((pull_requests, error), ([], None))
        command = gh_call.call_args.args[1]
        self.assertIn("--repo", command)
        self.assertNotIn("statusCheckRollup", command)

    def test_remote_selection_is_exact(self) -> None:
        self.assertEqual(pr_preflight.select_remote(["origin", "upstream"], "origin"), "origin")
        with self.assertRaises(pr_preflight.PreflightError):
            pr_preflight.select_remote(["origin"], "missing")

    def test_repo_must_stay_inside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            repo = workspace / "repo"
            outside = Path(tmp) / "outside"
            repo.mkdir(parents=True)
            outside.mkdir()
            pr_preflight.ensure_within_workspace(repo, workspace)
            with self.assertRaises(pr_preflight.PreflightError):
                pr_preflight.ensure_within_workspace(outside, workspace)

    def test_sensitive_output_is_redacted(self) -> None:
        raw = (
            "password=example-value https://user:example-value@example.invalid/repo "
            "Authorization: Bearer example-bearer-value"
        )
        cleaned = pr_preflight.strip_sensitive(raw)
        self.assertNotIn("example-value", cleaned)
        self.assertNotIn("example-bearer-value", cleaned)
        self.assertIn("<redacted>", cleaned)


class ChatHistoryTests(unittest.TestCase):
    def make_claude_session(self, root: Path, session_id: str, cwd: Path) -> Path:
        path = root / f"{session_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        records = [
            {
                "type": "user",
                "cwd": str(cwd),
                "message": {"role": "user", "content": "hello"},
            },
            {
                "type": "assistant",
                "cwd": str(cwd),
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "call-1",
                            "name": "Bash",
                            "input": {"command": "find ."},
                        }
                    ],
                },
            },
            {
                "type": "user",
                "cwd": str(cwd),
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "call-1",
                            "content": "permission denied",
                            "is_error": True,
                        }
                    ],
                },
            },
        ]
        path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        return path

    def make_codex_session(self, root: Path, session_id: str, cwd: Path) -> Path:
        path = root / "2026" / "07" / "22" / f"rollout-2026-07-22T00-00-00-{session_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        records = [
            {"type": "session_meta", "payload": {"cwd": str(cwd), "id": session_id}},
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hello"}],
                },
            },
        ]
        path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        return path

    def test_codex_discovery_is_limited_to_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "workspace"
            workspace.mkdir()
            codex = base / "sessions"
            self.make_codex_session(
                codex,
                "aaaaaaaa-0000-0000-0000-000000000001",
                workspace / "repo",
            )
            self.make_codex_session(
                codex,
                "bbbbbbbb-0000-0000-0000-000000000002",
                base / "unrelated",
            )
            config = chat_history.Config(
                workspace=workspace,
                claude_project_dir=base / "claude",
                codex_sessions_dir=codex,
            )
            sessions = chat_history.discover_sessions(config, source="codex")
            self.assertEqual([session.session_id for session in sessions], [
                "aaaaaaaa-0000-0000-0000-000000000001"
            ])

    def test_claude_tool_call_is_paired_with_its_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "workspace"
            workspace.mkdir()
            claude = base / "claude"
            self.make_claude_session(
                claude,
                "dddddddd-0000-0000-0000-000000000004",
                workspace,
            )
            config = chat_history.Config(workspace, claude, base / "codex")
            sessions = chat_history.discover_sessions(config, source="claude")
            self.assertEqual(len(sessions), 1)
            messages, pairs = chat_history.parse_session(sessions[0])
            self.assertEqual(messages, [("user", "hello")])
            self.assertEqual(len(pairs), 1)
            self.assertEqual(pairs[0]["cmd"], "find .")
            self.assertFalse(pairs[0]["ok"])

    def test_large_session_metadata_is_still_discovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "workspace"
            workspace.mkdir()
            codex = base / "sessions"
            path = self.make_codex_session(
                codex,
                "cccccccc-0000-0000-0000-000000000003",
                workspace,
            )
            with path.open("a", encoding="utf-8") as handle:
                handle.write(" " * (1024 * 1024 + 1))
            config = chat_history.Config(workspace, base / "claude", codex)
            sessions = chat_history.discover_sessions(config, source="codex")
            self.assertEqual(len(sessions), 1)

    def test_session_prefix_rejects_globs_and_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            workspace = base / "workspace"
            workspace.mkdir()
            codex = base / "sessions"
            self.make_codex_session(
                codex,
                "aaaaaaaa-0000-0000-0000-000000000001",
                workspace,
            )
            self.make_codex_session(
                codex,
                "aaaaaaaa-0000-0000-0000-000000000002",
                workspace,
            )
            config = chat_history.Config(workspace, base / "claude", codex)
            with self.assertRaises(chat_history.HistoryError):
                chat_history.resolve_session(config, "*")
            with self.assertRaises(chat_history.HistoryError):
                chat_history.resolve_session(config, "aaaaaaaa")

    def test_history_output_redacts_sensitive_values(self) -> None:
        cleaned = chat_history.redact(
            "password=example-value Authorization: Bearer example-bearer-value"
        )
        self.assertNotIn("example-value", cleaned)
        self.assertNotIn("example-bearer-value", cleaned)
        self.assertIn("<redacted>", cleaned)

    def test_find_exit_one_remains_a_failure(self) -> None:
        self.assertFalse(chat_history.decide_ok("find .", "", False, 1))
        self.assertTrue(chat_history.decide_ok("rg missing .", "", False, 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
