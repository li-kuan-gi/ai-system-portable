#!/usr/bin/env python3
"""Inspect workspace-scoped Claude Code and Codex conversation history.

The helper reads service-managed session files but never packages or modifies
them. Session metadata must identify a working directory inside the installed
workspace. Printed prompts, commands, and tool results receive best-effort
sensitive-value redaction and bounded output.
"""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[3]
MAX_SESSION_BYTES = 128 * 1024 * 1024
MAX_CAPTURE_CHARS = 32_000
MAX_SESSIONS_DEFAULT = 500
UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
SESSION_PREFIX_RE = re.compile(r"[0-9a-f][0-9a-f-]{7,35}", re.IGNORECASE)
EXIT_CODE_RE = re.compile(r"(?:exited with code|Process exited with code)\s+(\d+)", re.IGNORECASE)

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

CATEGORIES = [
    ("patch", r"apply_patch|patchlog"),
    ("git", r"^\s*git\b|^\s*git -C\b|git-worktree|\bgh\b"),
    ("build", r"mvnw|\bmvn\b|gradle|npm|pnpm|yarn|cargo|go test"),
    ("database", r"sqlplus|\bpsql\b|psycopg|oracledb|cx_Oracle|pymssql|sqlcmd|\bisql\b"),
    ("container", r"\bdocker\b|podman|containerd|registry"),
    ("api", r"\bcurl\b|httpie|api[-_]call"),
    ("filesystem", r"^\s*(find|rg|grep|sed|ls|stat|cat|head|tail)\b"),
]

DENIED = re.compile(
    r"Denied by user|doesn't want to proceed with this tool|tool use was rejected|user rejected",
    re.IGNORECASE,
)
BLOCKED = re.compile(
    r"\[guard\] rejected|blocked by safety-net|not in (the )?(allowlist|whitelist)"
    r"|permissionDecision.?deny|policy (denied|blocked)|hook.*(deny|blocked)"
    r"|不在.*(允許|可信|白名單)|安全網.*(拒絕|阻擋)",
    re.IGNORECASE,
)
NOISE_LINE = re.compile(
    r"The user's next message may contain a correction|^<system-reminder|^Chunk ID:|"
    r"^Wall time:|^Process exited|^Original token count:|^Output:$|^\s*$"
)
STRONG_ERROR = re.compile(
    r"error|forbidden|exception|fail|denied|not found|refused|cannot|fatal|ORA-\d|"
    r"HTTP\s*0|traceback|usage:|could not resolve|not permitted|permission denied|"
    r"no such file|supported targets|E\d{3}|bwrap|returned \d{3}",
    re.IGNORECASE,
)


class HistoryError(ValueError):
    """Raised when a history query is invalid or crosses a safety boundary."""


@dataclass(frozen=True)
class Config:
    workspace: Path
    claude_project_dir: Path
    codex_sessions_dir: Path


@dataclass(frozen=True)
class Session:
    mtime: float
    session_id: str
    path: Path
    kind: str


def build_config() -> Config:
    workspace = ROOT.resolve()
    project_name = "-" + str(workspace).lstrip("/").replace("/", "-")
    claude = Path(
        os.environ.get(
            "CLAUDE_PROJECT_DIR",
            str(Path.home() / ".claude" / "projects" / project_name),
        )
    ).expanduser()
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    codex = Path(os.environ.get("CODEX_SESSIONS_DIR", str(codex_home / "sessions"))).expanduser()
    return Config(workspace=workspace, claude_project_dir=claude, codex_sessions_dir=codex)


def is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def redact(text: str, limit: int | None = None) -> str:
    text = ANSI_ESCAPE.sub("", str(text).replace("\r", ""))
    text = CONTROL.sub("", text)
    text = PEM_BLOCK.sub("<redacted-private-key>", text)
    text = URI_USERINFO.sub(r"\1<redacted>@", text)
    text = TOKEN_VALUE.sub("<redacted-token>", text)
    text = BEARER_VALUE.sub("Bearer <redacted>", text)
    text = SECRET_ASSIGNMENT.sub(lambda match: match.group(1) + match.group(2) + "<redacted>", text)
    if limit is not None and len(text) > limit:
        return text[:limit] + "..."
    return text


def clean(text: str) -> str:
    text = re.sub(
        r"<(system-reminder|command-[a-z-]+|local-command-[a-z-]+)[^>]*>.*?</\1>",
        " ",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"</?[a-z][a-z0-9-]*[^>]*>", " ", text)
    return " ".join(redact(text).split())


def iter_json_records(
    path: Path,
    max_bytes: int = MAX_SESSION_BYTES,
    allow_truncated: bool = False,
) -> Iterator[dict[str, Any]]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise HistoryError(f"cannot stat session file: {exc}") from exc
    if size > max_bytes and not allow_truncated:
        raise HistoryError(f"session exceeds {max_bytes} byte read limit")
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            consumed = 0
            for line in handle:
                consumed += len(line.encode("utf-8", errors="replace"))
                if consumed > max_bytes:
                    break
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(record, dict):
                    yield record
    except OSError as exc:
        raise HistoryError(f"cannot read session file: {exc}") from exc


def recorded_cwd(path: Path, kind: str) -> Path | None:
    for index, record in enumerate(
        iter_json_records(path, max_bytes=1024 * 1024, allow_truncated=True)
    ):
        raw: Any = None
        if kind == "codex" and record.get("type") == "session_meta":
            payload = record.get("payload")
            if isinstance(payload, dict):
                raw = payload.get("cwd")
        elif kind == "claude":
            raw = record.get("cwd")
        if isinstance(raw, str) and raw.strip():
            return Path(raw).expanduser().resolve()
        if index >= 199:
            break
    return None


def session_id_from_path(path: Path) -> str | None:
    match = UUID_RE.search(path.name)
    return match.group(0).lower() if match else None


def _candidate_paths(config: Config, source: str) -> Iterator[tuple[Path, str, Path]]:
    if source not in {"claude", "codex", "both"}:
        raise HistoryError(f"unsupported history source: {source}")
    if source in {"claude", "both"} and config.claude_project_dir.is_dir():
        for path in config.claude_project_dir.glob("*.jsonl"):
            yield path, "claude", config.claude_project_dir
    if source in {"codex", "both"} and config.codex_sessions_dir.is_dir():
        for path in config.codex_sessions_dir.rglob("rollout-*.jsonl"):
            yield path, "codex", config.codex_sessions_dir


def discover_sessions(
    config: Config,
    source: str = "both",
    since: float | None = None,
    max_sessions: int = MAX_SESSIONS_DEFAULT,
) -> list[Session]:
    workspace = config.workspace.expanduser().resolve()
    sessions: list[Session] = []
    for path, kind, source_root in _candidate_paths(config, source):
        try:
            if path.is_symlink() or not path.is_file():
                continue
            resolved = path.resolve()
            root = source_root.expanduser().resolve()
            if resolved != root and not is_under(resolved, root):
                continue
            mtime = resolved.stat().st_mtime
            if since is not None and mtime < since:
                continue
            session_id = session_id_from_path(resolved)
            cwd = recorded_cwd(resolved, kind)
        except (HistoryError, OSError):
            continue
        if session_id is None or cwd is None:
            continue
        if cwd != workspace and not is_under(cwd, workspace):
            continue
        sessions.append(Session(mtime, session_id, resolved, kind))
    sessions.sort(key=lambda session: (session.mtime, session.session_id))
    if max_sessions > 0 and len(sessions) > max_sessions:
        sessions = sessions[-max_sessions:]
    return sessions


def resolve_session(config: Config, prefix: str, source: str = "both") -> Session:
    normalized = prefix.strip().lower()
    if not SESSION_PREFIX_RE.fullmatch(normalized):
        raise HistoryError("session id must be an 8-36 character hexadecimal UUID prefix")
    matches = [
        session
        for session in discover_sessions(config, source=source, max_sessions=0)
        if session.session_id.startswith(normalized)
    ]
    if not matches:
        raise HistoryError(f"no workspace session matches: {prefix}")
    if len(matches) > 1:
        raise HistoryError(f"session prefix is ambiguous ({len(matches)} matches): {prefix}")
    return matches[0]


def categorize(command: str) -> str:
    for name, pattern in CATEGORIES:
        if re.search(pattern, command or ""):
            return name
    return "other"


def decide_ok(command: str, output: str, raw_ok: bool, code: int | None) -> bool:
    if raw_ok:
        return True
    command = (command or "").strip()
    output = output or ""
    hard = re.search(
        r"No such file|Permission denied|os error|not permitted|cannot|fatal|Traceback|"
        r"Forbidden|refused|COMPILATION ERROR|Exception",
        output,
        re.IGNORECASE,
    )
    if re.match(r"(\S*/)?(rg|grep|egrep|fgrep)\b", command):
        if code == 1 and not hard:
            return True
        if code is None and not hard:
            return True
    if re.match(r"(\S*/)?(diff|cmp)\b", command) and code == 1 and not hard:
        return True
    if re.match(r"(command -v|which|type)\b", command):
        return True
    if re.search(r"\bgh\b.*\b(view|list|status)\b", command) and re.search(
        r"no .*found|not found", output, re.IGNORECASE
    ):
        return True
    return raw_ok


def outcome_kind(ok: bool, output: str) -> str:
    if ok:
        return "ok"
    if DENIED.search(output or ""):
        return "denied"
    if BLOCKED.search(output or ""):
        return "blocked"
    return "fail"


def _capture(value: Any) -> str:
    if isinstance(value, str):
        return value[:MAX_CAPTURE_CHARS]
    return json.dumps(value, ensure_ascii=False)[:MAX_CAPTURE_CHARS]


def parse_claude(path: Path) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
    messages: list[tuple[str, str]] = []
    calls: dict[str, dict[str, str]] = {}
    pairs: list[dict[str, Any]] = []
    for record in iter_json_records(path):
        if record.get("type") not in {"user", "assistant"}:
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            if content.strip():
                messages.append((str(message.get("role", "")), _capture(content.strip())))
            continue
        if not isinstance(content, list):
            continue
        texts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                texts.append(_capture(block.get("text", "")))
            elif block_type == "tool_use":
                tool_input = block.get("input")
                command = ""
                if isinstance(tool_input, dict):
                    command = str(
                        tool_input.get("command")
                        or tool_input.get("file_path")
                        or tool_input.get("pattern")
                        or _capture(tool_input)
                    )
                calls[str(block.get("id", ""))] = {
                    "tool": str(block.get("name", "")),
                    "cmd": _capture(command),
                }
            elif block_type == "tool_result":
                result_content = block.get("content")
                if isinstance(result_content, list):
                    result_content = " ".join(
                        str(item.get("text", ""))
                        for item in result_content
                        if isinstance(item, dict)
                    )
                output = _capture(result_content)
                info = calls.get(str(block.get("tool_use_id", "")), {"tool": "?", "cmd": ""})
                ok = decide_ok(info["cmd"], output, not bool(block.get("is_error")), None)
                pairs.append({"tool": info["tool"], "cmd": info["cmd"], "ok": ok, "out": output})
        text = " ".join(item for item in texts if item).strip()
        if text:
            messages.append((str(message.get("role", "")), _capture(text)))
    return messages, pairs


def _codex_exit_code(output: Any) -> int | None:
    if isinstance(output, dict):
        metadata = output.get("metadata")
        if isinstance(metadata, dict) and metadata.get("exit_code") is not None:
            try:
                return int(metadata["exit_code"])
            except (TypeError, ValueError):
                return None
    if isinstance(output, str):
        match = EXIT_CODE_RE.search(output)
        if match:
            return int(match.group(1))
        try:
            decoded = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return None
        return _codex_exit_code(decoded)
    return None


def parse_codex(path: Path) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
    messages: list[tuple[str, str]] = []
    calls: dict[str, dict[str, str]] = {}
    pairs: list[dict[str, Any]] = []
    for record in iter_json_records(path):
        if record.get("type") != "response_item":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        subtype = payload.get("type")
        if subtype == "message":
            role = str(payload.get("role", ""))
            if role not in {"user", "assistant"}:
                continue
            content = payload.get("content")
            if not isinstance(content, list):
                continue
            text = " ".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict)
                and item.get("type") in {"input_text", "output_text"}
            ).strip()
            if text:
                messages.append((role, _capture(text)))
        elif subtype in {"function_call", "custom_tool_call"}:
            command = ""
            if subtype == "function_call":
                try:
                    arguments = json.loads(str(payload.get("arguments", "{}")))
                except json.JSONDecodeError:
                    arguments = None
                if isinstance(arguments, dict):
                    command_value = arguments.get("cmd") or arguments.get("command") or ""
                    if isinstance(command_value, list):
                        command_value = " ".join(str(item) for item in command_value)
                    command = str(command_value)
                else:
                    command = str(payload.get("arguments", ""))
            else:
                command = str(payload.get("input", ""))
            calls[str(payload.get("call_id", ""))] = {
                "tool": str(payload.get("name", "")),
                "cmd": _capture(command),
            }
        elif subtype in {"function_call_output", "custom_tool_call_output"}:
            output_value = payload.get("output", "")
            output = _capture(output_value)
            info = calls.get(str(payload.get("call_id", "")), {"tool": "?", "cmd": ""})
            code = _codex_exit_code(output_value)
            has_error = bool(payload.get("is_error")) or (
                isinstance(output_value, dict) and bool(output_value.get("error"))
            )
            raw_ok = (code == 0) if code is not None else not has_error
            ok = decide_ok(info["cmd"], output, raw_ok, code)
            pairs.append({"tool": info["tool"], "cmd": info["cmd"], "ok": ok, "out": output})
    return messages, pairs


def parse_session(session: Session) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
    return parse_claude(session.path) if session.kind == "claude" else parse_codex(session.path)


def representative_error(output: str) -> str:
    lines = [
        line.strip()
        for line in (output or "").splitlines()
        if line.strip() and not NOISE_LINE.search(line.strip())
    ]
    for line in lines:
        if STRONG_ERROR.search(line):
            return redact(line, 140)
    return redact(lines[-1], 140) if lines else "(no output)"


def parse_since(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").timestamp()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def _safe_parse(session: Session) -> tuple[list[tuple[str, str]], list[dict[str, Any]]] | None:
    try:
        return parse_session(session)
    except HistoryError as exc:
        print(f"chat-history: skip {session.session_id[:8]}: {exc}", file=sys.stderr)
        return None


def command_prompts(args: argparse.Namespace, config: Config) -> int:
    rows: list[tuple[str, str, str, int, str]] = []
    for session in discover_sessions(config, args.source, args.since, args.max_sessions):
        parsed = _safe_parse(session)
        if parsed is None:
            continue
        messages, _ = parsed
        prompts = [clean(text) for role, text in messages if role == "user"]
        prompts = [item for item in prompts if item and not item.startswith(("Caveat:", "[Request"))]
        if not prompts:
            continue
        date = datetime.datetime.fromtimestamp(session.mtime).strftime("%m-%d")
        rows.append((date, session.session_id[:8], session.kind[0], len(prompts), prompts[0][:140]))
    for date, session_id, kind, count, first_prompt in rows:
        print(f"{date} {session_id} {kind} t={count:<3} {first_prompt}")
    print(f"\nTOTAL: {len(rows)} sessions")
    return 0


def command_dump(args: argparse.Namespace, config: Config) -> int:
    for prefix in args.session_ids:
        session = resolve_session(config, prefix, args.source)
        parsed = parse_session(session)
        messages = [
            (role, text)
            for role, text in parsed[0]
            if not clean(text).startswith(("# AGENTS.md", "Caveat:"))
        ]
        print("=" * 80)
        print(f"### {session.session_id[:8]} [{session.kind}] msgs={len(messages)}")
        shown = messages[-args.tail :] if args.tail else messages
        for role, text in shown:
            cap = 350 if role == "user" else args.assistant_cap
            print(f"\n[{'U' if role == 'user' else 'A'}] {clean(text)[:cap]}")
    return 0


FLAGS = {"ok": "OK  ", "fail": "FAIL", "denied": "DENY", "blocked": "BLOK"}


def command_tools(args: argparse.Namespace, config: Config) -> int:
    for prefix in args.session_ids:
        session = resolve_session(config, prefix, args.source)
        _, pairs = parse_session(session)
        print("=" * 80)
        print(f"### {session.session_id[:8]} [{session.kind}] tool-calls={len(pairs)}")
        for pair in pairs:
            category = categorize(pair["cmd"] + " " + pair["tool"])
            if args.category and category != args.category:
                continue
            kind = outcome_kind(pair["ok"], pair["out"])
            if args.fails_only and kind == "ok":
                continue
            line = clean(pair["cmd"] or pair["tool"])[:110]
            print(f"  [{FLAGS[kind]}] {category:11} {clean(pair['tool'])[:14]:14} {line}")
            if kind != "ok":
                print(f"         ! {representative_error(pair['out'])}")
    return 0


def command_fails(args: argparse.Namespace, config: Config) -> int:
    failures = collections.Counter()
    total_calls = collections.Counter()
    outcomes = collections.Counter()
    fail_signatures = collections.Counter()
    denied_signatures = collections.Counter()
    blocked_signatures = collections.Counter()
    examples: dict[tuple[str, str, str], str] = {}
    session_count = 0
    for session in discover_sessions(config, args.source, args.since, args.max_sessions):
        parsed = _safe_parse(session)
        if parsed is None:
            continue
        session_count += 1
        _, pairs = parsed
        for pair in pairs:
            category = categorize(pair["cmd"] + " " + pair["tool"])
            total_calls[category] += 1
            kind = outcome_kind(pair["ok"], pair["out"])
            outcomes[kind] += 1
            if kind == "ok" or (args.category and category != args.category):
                continue
            signature = representative_error(pair["out"])
            date = datetime.datetime.fromtimestamp(session.mtime).strftime("%m-%d")
            command = clean(pair["cmd"] or pair["tool"])[:70]
            example = f"{date} {session.session_id[:8]} {session.kind[0]}: {command}"
            if kind == "fail":
                failures[category] += 1
                fail_signatures[(category, signature)] += 1
                examples.setdefault(("fail", category, signature), example)
            elif kind == "denied":
                command_signature = command[:60]
                denied_signatures[(category, command_signature)] += 1
                examples.setdefault(("denied", category, command_signature), example)
            else:
                blocked_signatures[(category, signature)] += 1
                examples.setdefault(("blocked", category, signature), example)

    print(
        f"Scanned {session_count} sessions. outcomes: ok={outcomes['ok']} "
        f"fail={outcomes['fail']} denied={outcomes['denied']} blocked={outcomes['blocked']}"
    )
    print("(outcome uses paired tool results; denied/blocked are not execution failures)\n")
    print("REAL execution failures by category (denied/blocked excluded):")
    print(f"  {'category':12} {'fails':>6} {'/calls':>7}")
    categories = sorted(set(failures) | set(total_calls), key=lambda item: -failures[item])
    for category in categories:
        if args.category and category != args.category:
            continue
        print(f"  {category:12} {failures[category]:>6} {total_calls[category]:>7}")
    print(f"  {'TOTAL':12} {sum(failures.values()):>6} {sum(total_calls.values()):>7}")
    print("\n  top fail signatures:")
    for (category, signature), count in fail_signatures.most_common(15):
        print(f"    x{count:<3} [{category}] {signature}")
        print(f"          e.g. {examples[('fail', category, signature)]}")
    print(f"\nUSER-DENIED tool calls (over-prompting signal): {outcomes['denied']}")
    for (category, signature), count in denied_signatures.most_common(15):
        print(f"    x{count:<3} [{category}] {signature}")
        print(f"          e.g. {examples[('denied', category, signature)]}")
    print(f"\nPOLICY/GUARD rejections (safety-net working): {outcomes['blocked']}")
    for (category, signature), count in blocked_signatures.most_common(10):
        print(f"    x{count:<3} [{category}] {signature}")
        print(f"          e.g. {examples[('blocked', category, signature)]}")
    return 0


def command_grep(args: argparse.Namespace, config: Config) -> int:
    pattern = args.pattern if args.regex else re.escape(args.pattern)
    try:
        matcher = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise HistoryError(f"invalid regular expression: {exc}") from exc
    for session in discover_sessions(config, args.source, args.since, args.max_sessions):
        parsed = _safe_parse(session)
        if parsed is None:
            continue
        messages, pairs = parsed
        hits: list[tuple[str, str]] = []
        if args.where in {"prompt", "both"}:
            for role, text in messages:
                cleaned = clean(text)
                if role == "user" and matcher.search(cleaned):
                    hits.append(("U", cleaned[:120]))
        if args.where in {"output", "both"}:
            for pair in pairs:
                if matcher.search(pair["out"] or ""):
                    kind = outcome_kind(pair["ok"], pair["out"])
                    hits.append(("O:" + kind, representative_error(pair["out"])))
        if hits:
            date = datetime.datetime.fromtimestamp(session.mtime).strftime("%m-%d")
            print(f"{date} {session.session_id[:8]} {session.kind[0]} ({len(hits)} hits)")
            for tag, hit in hits[:3]:
                print(f"    [{tag}] {hit}")
    return 0


def _add_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", choices=("claude", "codex", "both"), default="both")


def _add_scan_bounds(parser: argparse.ArgumentParser) -> None:
    _add_source(parser)
    parser.add_argument("--since", type=parse_since, metavar="YYYY-MM-DD")
    parser.add_argument("--max-sessions", type=int, default=MAX_SESSIONS_DEFAULT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect workspace-scoped Claude Code and Codex conversation history."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prompts = subparsers.add_parser("prompts", help="list first user prompt per session")
    _add_scan_bounds(prompts)
    prompts.set_defaults(handler=command_prompts)

    dump = subparsers.add_parser("dump", help="print a bounded transcript")
    dump.add_argument("session_ids", nargs="+")
    _add_source(dump)
    dump.add_argument("--tail", type=int)
    dump.add_argument("--assistant-cap", type=int, default=900)
    dump.set_defaults(handler=command_dump)

    tools = subparsers.add_parser("tools", help="list paired tool calls and outcomes")
    tools.add_argument("session_ids", nargs="+")
    _add_source(tools)
    tools.add_argument("--category")
    tools.add_argument("--fails-only", action="store_true")
    tools.set_defaults(handler=command_tools)

    fails = subparsers.add_parser("fails", help="aggregate paired tool outcomes")
    _add_scan_bounds(fails)
    fails.add_argument("--category")
    fails.set_defaults(handler=command_fails)

    grep = subparsers.add_parser("grep", help="find literal text in prompts or tool outputs")
    grep.add_argument("pattern")
    _add_scan_bounds(grep)
    grep.add_argument("--in", dest="where", choices=("prompt", "output", "both"), default="both")
    grep.add_argument("--regex", action="store_true", help="treat pattern as a regular expression")
    grep.set_defaults(handler=command_grep)
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "max_sessions", 1) < 1:
        parser.error("--max-sessions must be at least 1")
    if getattr(args, "tail", 1) is not None and getattr(args, "tail", 1) < 1:
        parser.error("--tail must be at least 1")
    if getattr(args, "assistant_cap", 1) < 1:
        parser.error("--assistant-cap must be at least 1")
    try:
        return int(args.handler(args, build_config()))
    except HistoryError as exc:
        print(f"chat-history: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
