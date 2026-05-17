#!/usr/bin/env python3
"""Append one validated patchlog entry.

This helper is intentionally narrow: it only appends to existing patchlog files
inside the workspace and verifies after writing that the previous content was
left untouched.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CENTRAL_PATCHLOG = ROOT / "ai-system" / "governance" / "patchlog.md"
VALID_REVISION_TYPES = {"補缺", "補欄位", "正規提案"}
MAX_FIELD_CHARS = 2000

SUSPICIOUS_VALUE_PATTERNS = [
    re.compile(
        r"(?i)\b(authorization|bearer|token|password|passwd|secret|api[_-]?key|client[_-]?secret|cookie)\b"
        r"\s*[:=]\s*['\"]?[^'\"\s]{6,}"
    ),
    re.compile(r"(?i)\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*(PRIVATE KEY|CERTIFICATE)-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]

PACKAGE_LEVEL_FILES = {
    "AGENTS.md",
    "README.md",
    "PORTABILITY.md",
    "SERVICE_PORTABILITY.md",
}

PACKAGE_PATH_PREFIXES = (
    "ai-system/",
    "scripts/",
    "templates/",
    "service-packs/",
    "implementation-packs/",
)


class ValidationError(Exception):
    pass


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 2


def nonblank(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(f"{field} is required")
    if len(cleaned) > MAX_FIELD_CHARS:
        raise ValidationError(f"{field} exceeds {MAX_FIELD_CHARS} characters")
    return cleaned


def resolve_patchlog(raw: str) -> tuple[Path, str]:
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    resolved = path.resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError as exc:
        raise ValidationError("patchlog must be inside the workspace") from exc
    if not resolved.exists() or not resolved.is_file():
        raise ValidationError("patchlog must be an existing file")
    if resolved == CENTRAL_PATCHLOG:
        return resolved, "central"
    raise ValidationError("patchlog target is not allowlisted")


def validate_changed_files(files: list[str], scope: str) -> list[str]:
    if not files:
        raise ValidationError("at least one --changed-file is required")
    cleaned: list[str] = []
    for raw in files:
        item = nonblank(raw, "changed-file")
        if item.startswith("/") or ".." in Path(item).parts:
            raise ValidationError(f"changed-file must be a safe relative path: {item}")
        if scope == "central" and item not in PACKAGE_LEVEL_FILES and not item.startswith(PACKAGE_PATH_PREFIXES):
            raise ValidationError("central patchlog only records portable package changes")
        cleaned.append(item)
    return cleaned


def validate_evidence(values: list[str]) -> list[str]:
    if not values:
        raise ValidationError("at least one --evidence is required")
    cleaned = [nonblank(value, "evidence") for value in values]
    joined = "\n".join(cleaned).lower()
    weak_markers = ("agent guess", "agent 推測", "推測", "假設", "猜測")
    if all(any(marker in item.lower() for marker in weak_markers) for item in cleaned):
        raise ValidationError("evidence cannot be only an agent guess or assumption")
    source_markers = (
        "user",
        "local check",
        "document",
        "code",
        "runtime",
        "api",
        "db",
        "log",
        "使用者",
        "本機檢查",
    )
    if not any(marker in joined for marker in source_markers):
        raise ValidationError(
            "evidence should name a concrete source, such as user request, local check, document, code path, runtime, API, DB, or log result"
        )
    return cleaned


def reject_sensitive_values(text: str) -> None:
    for pattern in SUSPICIOUS_VALUE_PATTERNS:
        if pattern.search(text):
            raise ValidationError("entry appears to contain a sensitive credential value")


def build_entry(args: argparse.Namespace, scope: str) -> str:
    subject = nonblank(args.subject, "subject")
    revision_type = nonblank(args.revision_type, "revision-type")
    if revision_type not in VALID_REVISION_TYPES:
        raise ValidationError(f"revision-type must be one of: {', '.join(sorted(VALID_REVISION_TYPES))}")
    summary = nonblank(args.summary, "summary")
    context = nonblank(args.context, "context")
    changed_files = validate_changed_files(args.changed_file, scope)
    evidence = validate_evidence(args.evidence)
    entry_date = nonblank(args.date, "date")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry_date):
        raise ValidationError("date must use YYYY-MM-DD")

    changed = " / ".join(changed_files)
    evidence_lines = "\n".join(f"- {item}" for item in evidence)
    entry = (
        f"## {entry_date} · {subject} · {changed}\n\n"
        f"**修訂類型**：{revision_type}\n"
        f"**變更摘要**：{summary}\n"
        f"**來源證據**：\n"
        f"{evidence_lines}\n"
        f"**任務情境**：{context}\n"
    )
    reject_sensitive_values(entry)
    return entry


def append_entry(path: Path, entry: str, dry_run: bool) -> None:
    before = path.read_text(encoding="utf-8")
    separator = "" if not before else ("\n" if before.endswith("\n") else "\n\n")
    appended = separator + entry
    after = before + appended
    if not after.startswith(before):
        raise ValidationError("internal append check failed before writing")
    if dry_run:
        print(entry, end="")
        return

    with path.open("a", encoding="utf-8") as fh:
        fh.write(appended)
    reread = path.read_text(encoding="utf-8")
    if not reread.startswith(before) or reread[len(before) :] != appended:
        raise ValidationError("post-write check failed: patchlog was not append-only")
    print(f"appended patchlog entry: {path.relative_to(ROOT)}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append one validated patchlog entry")
    parser.add_argument("--patchlog", default="ai-system/governance/patchlog.md")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--subject", required=True)
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--revision-type", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--context", required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    try:
        args = parse_args(argv)
        patchlog, scope = resolve_patchlog(args.patchlog)
        entry = build_entry(args, scope)
        append_entry(patchlog, entry, args.dry_run)
        return 0
    except ValidationError as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
