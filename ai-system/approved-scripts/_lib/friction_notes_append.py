#!/usr/bin/env python3
"""Append one validated friction note.

This helper is intentionally narrow: it only appends to the central friction
notes file and verifies after writing that the previous content was left
untouched.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CENTRAL_FRICTION_NOTES = ROOT / "ai-system" / "governance" / "friction_notes.md"
APPEND_SECTION = "## 待處理追加紀錄"
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


class ValidationError(Exception):
    pass


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 2


def compact(value: str, field: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise ValidationError(f"{field} is required")
    if len(cleaned) > MAX_FIELD_CHARS:
        raise ValidationError(f"{field} exceeds {MAX_FIELD_CHARS} characters")
    return cleaned


def resolve_notes(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    resolved = path.resolve()
    if resolved != CENTRAL_FRICTION_NOTES:
        raise ValidationError("notes target is not allowlisted")
    if not resolved.exists() or not resolved.is_file():
        raise ValidationError("notes target must be an existing file")
    return resolved


def validate_evidence(values: list[str]) -> list[str]:
    if not values:
        raise ValidationError("at least one --evidence is required")
    cleaned = [compact(value, "evidence") for value in values]
    weak_markers = ("agent guess", "agent 推測", "推測", "假設", "猜測")
    if all(any(marker in item.lower() for marker in weak_markers) for item in cleaned):
        raise ValidationError("evidence cannot be only an agent guess or assumption")
    joined = "\n".join(cleaned).lower()
    source_markers = (
        "user",
        "local check",
        "document",
        "code",
        "runtime",
        "api",
        "db",
        "log",
        "trace",
        "issue",
        "使用者",
        "老闆",
        "對話",
        "本機檢查",
        "文件",
    )
    if not any(marker in joined for marker in source_markers):
        raise ValidationError(
            "evidence should name a concrete source, such as user request, local check, document, code path, runtime, API result, log, trace, or issue tracker item"
        )
    return cleaned


def validate_list(values: list[str], field: str) -> list[str]:
    if not values:
        raise ValidationError(f"at least one --{field} is required")
    return [compact(value, field) for value in values]


def reject_sensitive_values(text: str) -> None:
    for pattern in SUSPICIOUS_VALUE_PATTERNS:
        if pattern.search(text):
            raise ValidationError("entry appears to contain a sensitive credential value")


def validate_append_section(existing: str) -> None:
    last_h2 = ""
    for line in existing.splitlines():
        if line.startswith("## "):
            last_h2 = line.strip()
    if last_h2 != APPEND_SECTION:
        raise ValidationError(f"notes file must end in the {APPEND_SECTION!r} section")


def build_entry(args: argparse.Namespace) -> str:
    title = compact(args.title, "title")
    symptom = compact(args.symptom, "symptom")
    friction = compact(args.friction, "friction")
    evidence = validate_evidence(args.evidence)
    reminders = validate_list(args.reminder, "reminder")
    absorb = validate_list(args.absorb, "absorb")
    entry_date = compact(args.date, "date")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry_date):
        raise ValidationError("date must use YYYY-MM-DD")

    evidence_lines = "\n".join(f"  - {item}" for item in evidence)
    reminder_lines = "\n".join(f"  - {item}" for item in reminders)
    absorb_lines = "\n".join(f"  - {item}" for item in absorb)
    entry = (
        f"### {title}\n\n"
        f"- **首次發現**：{entry_date}\n"
        f"- **現象**：{symptom}\n"
        f"- **來源證據**：\n"
        f"{evidence_lines}\n"
        f"- **為何屬制度摩擦**：{friction}\n"
        f"- **對後續 agent 的判斷提醒**：\n"
        f"{reminder_lines}\n"
        f"- **建議吸收方向**：\n"
        f"{absorb_lines}\n"
    )
    reject_sensitive_values(entry)
    return entry


def append_entry(path: Path, entry: str, dry_run: bool) -> None:
    before = path.read_text(encoding="utf-8")
    validate_append_section(before)
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
        raise ValidationError("post-write check failed: friction notes were not append-only")
    print(f"appended friction note: {path.relative_to(ROOT)}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append one validated friction note")
    parser.add_argument("--notes", default="ai-system/governance/friction_notes.md")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--title", required=True)
    parser.add_argument("--symptom", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--friction", required=True)
    parser.add_argument("--reminder", action="append", default=[])
    parser.add_argument("--absorb", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    try:
        args = parse_args(argv)
        notes = resolve_notes(args.notes)
        entry = build_entry(args)
        append_entry(notes, entry, args.dry_run)
        return 0
    except ValidationError as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
