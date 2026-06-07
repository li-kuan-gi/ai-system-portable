#!/usr/bin/env python3
"""Claude Code PreToolUse hook implementing the Bash slice of ai-system/safety-net.md.

兩個機械式決策（其他命令不輸出 decision，回到 Claude 正常 ask 流程）：

1. deny：未受控 detached / 長時間常駐服務（safety-net.md §2.3 forbidden）。
   `&` 背景化、`nohup`、`disown`、`setsid`、`docker compose up -d`、
   `pm2 start`、`mvn spring-boot:start`。引號內的 `&`、`&&`、`2>&1`、`&>` 不誤判。

2. allow：執行 `ai-system/approved-scripts/allow/` 下的 trusted script
   （safety-net.md §2.1 + approved-scripts/README.md 的目錄級消費）。
   為配合 agent 的自然寫法，允許以下「不會執行別的事、也不讀任意檔」的外殼：

       [ cd <workspace> (&& | ; | 換行) ]?
       <trusted-script> [args] [2>&1]?
       ( | <純輸出過濾器> [安全旗標] )*

   - 前綴 cd 只接受切到 workspace root。
   - pipe 只接受純輸出過濾器白名單（head/tail/cat/wc/nl），且這些過濾器
     只能帶旗標或數字，不能帶檔案路徑運算元（避免 `helper | cat /path/secret`
     之類繞過 hook 讀任意檔）；tail -f / -o 等會常駐或寫檔的旗標一律擋。
   - 仍擋：`$`/反引號展開、env assignment、interpreter option、`;`/`&&`/`&`
     命令串接或背景化、`>`/`<` 寫檔重導、額外換行、`||`。

   不符合上述外殼的命令一律 no_decision，回到手動 ask。

I/O 採 Claude Code PreToolUse hook 協定：
- stdin: {"hook_event_name":"PreToolUse","tool_name":"Bash","cwd":"...","tool_input":{"command":"..."}}
- stdout(allow/deny): {"hookSpecificOutput":{"hookEventName":"PreToolUse",
    "permissionDecision":"allow"|"deny","permissionDecisionReason":"..."}}
- stdout(no decision): 不輸出 JSON
"""
import json
import os
import re
import shlex
import sys
from pathlib import Path


TRUSTED_SCRIPT_DIR = Path(os.environ["TRUSTED_SCRIPT_DIR"]).expanduser().resolve()
EXPECTED_CWD_RAW = os.environ.get("EXPECTED_CWD")
EXPECTED_CWD = Path(EXPECTED_CWD_RAW).expanduser().resolve() if EXPECTED_CWD_RAW else None
# safety-net.md §1 / §2.1：git add / commit 只在 .worktrees/ 下 allow。
WORKTREES_DIR = (EXPECTED_CWD / ".worktrees") if EXPECTED_CWD is not None else None

# Shell 會在 parsing 前移除 backslash-newline；hook 要用同樣視角判斷。
LINE_CONTINUATION = re.compile(r"\\\r?\n[ \t]*")

ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")

INTERPRETERS = {"bash", "sh", "zsh", "python", "python3"}

# safety-net.md §2.3：未受控 detached 啟動長時間服務。在「移除引號內容」後偵測。
DETACHED_WORD = re.compile(r"(?<![\w./-])(nohup|disown|setsid)(?![\w./-])")
# 背景化 &：排除 &&（and-list）、&>（redirection）、>&/<&/數字-redirection（fd dup）。
BACKGROUND_AMP = re.compile(r"(?<![>&\d])&(?![&>])")
PM2_START = re.compile(r"(?<![\w./-])pm2\s+start(?![\w./-])")
SPRING_BOOT_START = re.compile(r"spring-boot:start")
DOCKER_COMPOSE_UP = re.compile(r"docker(?:-compose|\s+compose)\s+up\b")
DETACH_FLAG = re.compile(r"(?<![\w-])(?:-d|--detach)(?![\w-])")

# 允許保留串流的 redirect 合併（不寫檔）。
REDIR_MERGE_TOKENS = {"2>&1", ">&2", "1>&2"}

# pipe 只接受純輸出過濾器（不寫檔、不執行外部程式）。
SAFE_FILTERS = {"head", "tail", "cat", "wc", "nl"}
# 即使在 SAFE_FILTERS 內，這些旗標會常駐或寫檔，一律擋。
BANNED_FILTER_FLAGS = {"-f", "--follow", "-o", "--output", "-F"}

FILTER_SHORT_FLAG = re.compile(r"^-[A-Za-z]+$")
FILTER_NUM_FLAG = re.compile(r"^-[0-9]+$")
FILTER_LONG_FLAG = re.compile(r"^--[A-Za-z][A-Za-z-]*(=[0-9]+)?$")
FILTER_NUM_OPERAND = re.compile(r"^[0-9]+$")


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


def resolve_token_as_path(token: str, cwd: Path) -> Path:
    p = Path(token).expanduser()
    if not p.is_absolute():
        p = cwd / p
    return p.resolve()


def normalize_command(command: str) -> str:
    return LINE_CONTINUATION.sub(" ", command)


def strip_quoted(command: str) -> str:
    """把單/雙引號內容換成空白，保留結構供 detached / redirect 偵測。"""
    out = []
    in_single = in_double = escaped = False
    i = 0
    while i < len(command):
        ch = command[i]
        if escaped:
            out.append(" ")
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            out.append(" ")
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            out.append(" ")
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            out.append(" ")
            i += 1
            continue
        out.append(" " if (in_single or in_double) else ch)
        i += 1
    return "".join(out)


def has_active_expansion(command: str) -> bool:
    """偵測會被 shell 展開的 `$` / 反引號。單引號內為字面值；雙引號內仍會展開。"""
    in_single = in_double = escaped = False
    i = 0
    while i < len(command):
        ch = command[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if not in_single and (ch == "$" or ch == "`"):
            return True
        i += 1
    return False


def detached_service_reason(command: str) -> str | None:
    bare = strip_quoted(command)
    if BACKGROUND_AMP.search(bare):
        return "未受控背景化（trailing/standalone &）啟動，違反 safety-net.md §2.3；請用前景 session 或 approved wrapper。"
    m = DETACHED_WORD.search(bare)
    if m:
        return f"未受控 detached 啟動（{m.group(1)}），違反 safety-net.md §2.3；請用前景 session 或 approved wrapper。"
    if PM2_START.search(bare):
        return "pm2 start 屬未受控常駐服務，違反 safety-net.md §2.3；請用前景 session 或 approved wrapper。"
    if SPRING_BOOT_START.search(bare):
        return "spring-boot:start 屬未受控常駐服務，違反 safety-net.md §2.3；請改前景 run 或 approved wrapper。"
    if DOCKER_COMPOSE_UP.search(bare) and DETACH_FLAG.search(bare):
        return "docker compose up -d 屬未受控 detached 服務，違反 safety-net.md §2.3；請用前景或 approved wrapper。"
    return None


def find_cd_separator(s: str):
    """quote-aware 找第一個 top-level 的 cd 分隔符（換行 / ; / &&），回傳 (idx, len) 或 None。"""
    in_single = in_double = escaped = False
    i = 0
    while i < len(s):
        ch = s[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if not in_single and not in_double:
            if ch == "\n" or ch == ";":
                return (i, 1)
            if ch == "&" and i + 1 < len(s) and s[i + 1] == "&":
                return (i, 2)
        i += 1
    return None


def split_top_level_pipe(s: str) -> list[str]:
    """quote-aware 以單一 `|` 切段；`||` 會切出空段，由呼叫端視為不合法。"""
    segs = []
    cur = []
    in_single = in_double = escaped = False
    i = 0
    while i < len(s):
        ch = s[i]
        if escaped:
            cur.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            cur.append(ch)
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            cur.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            cur.append(ch)
            i += 1
            continue
        if ch == "|" and not in_single and not in_double:
            segs.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    segs.append("".join(cur))
    return segs


def split_top_level_and_list(s: str) -> list[str]:
    """quote-aware 以 top-level `&&` 或 `;` 切段（供 git add && git commit 這類組合驗證）。"""
    segs = []
    cur = []
    in_single = in_double = escaped = False
    i = 0
    while i < len(s):
        ch = s[i]
        if escaped:
            cur.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            cur.append(ch)
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            cur.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            cur.append(ch)
            i += 1
            continue
        if not in_single and not in_double:
            if ch == ";":
                segs.append("".join(cur))
                cur = []
                i += 1
                continue
            if ch == "&" and i + 1 < len(s) and s[i + 1] == "&":
                segs.append("".join(cur))
                cur = []
                i += 2
                continue
        cur.append(ch)
        i += 1
    segs.append("".join(cur))
    return segs


def split_optional_cd(command: str, base_cwd: Path):
    """處理可選的前綴 `cd <dir> (&&|;|換行)`。

    回傳 (remainder, cd_target_or_None)；cd_target 為解析後的絕對路徑。
    若有 cd-ish / 串接前綴但格式不合法，回傳 None（不自動核准）。
    """
    sep = find_cd_separator(command)
    if sep is None:
        return (command, None)  # 沒有 top-level 串接 → 整條當主體驗證

    idx, slen = sep
    prefix = command[:idx].strip()
    rest = command[idx + slen:].lstrip()

    try:
        ptoks = shlex.split(prefix, posix=True)
    except ValueError:
        return None

    if not ptoks or ptoks[0] != "cd":
        # 前綴不是 cd，卻有 top-level 串接 → 命令串接，不自動核准。
        return None

    if len(ptoks) == 2:
        return (rest, resolve_token_as_path(ptoks[1], base_cwd))

    return None  # cd 格式不符


def find_script_path(tokens: list[str], cwd: Path) -> Path | None:
    """裸執行（直接路徑 或 bash/python3 <script>），不接 interpreter option 或 env assignment。"""
    if not tokens:
        return None
    if ENV_ASSIGNMENT.match(tokens[0]):
        return None

    exe = tokens[0]
    exe_name = Path(exe).name

    if "/" in exe or exe.startswith("."):
        return resolve_token_as_path(exe, cwd)

    if exe_name in INTERPRETERS:
        if len(tokens) > 1 and tokens[1].startswith("-"):
            return None
        if len(tokens) > 1:
            return resolve_token_as_path(tokens[1], cwd)

    return None


def drop_redir_tokens(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in REDIR_MERGE_TOKENS]


def is_safe_filter_segment(segment: str) -> bool:
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        return False
    tokens = drop_redir_tokens(tokens)
    if not tokens:
        return False
    if tokens[0] not in SAFE_FILTERS:
        return False
    for t in tokens[1:]:
        if t in BANNED_FILTER_FLAGS:
            return False
        if FILTER_SHORT_FLAG.match(t):
            continue
        if FILTER_NUM_FLAG.match(t):
            continue
        if FILTER_LONG_FLAG.match(t):
            continue
        if FILTER_NUM_OPERAND.match(t):
            continue
        return False  # 任何路徑 / 文字運算元一律不放行
    return True


def extract_output_redirects(remainder: str, effective_cwd: Path):
    """抽掉「輸出重導到安全可寫路徑」（`>`/`>>`/`1>`/`2>` 到 /tmp 或 <workspace>/.worktrees），
    回傳去掉重導後、長度對齊的字串；若出現 input redirect(`<`)、無法驗證或不安全的目標、
    或殘留未辨識的輸出重導，回傳 None（→ 不自動核准）。

    安全性：目標用 resolve()（吃掉 `..`、symlink）後必須 is_under /tmp 或 .worktrees；
    引號內目標會被 strip_quoted 抹成空白而無法匹配 → 殘留 `>` → 回 None（保守擋）。
    """
    masked = strip_quoted(remainder)
    # 先把串流合併 token（2>&1 / >&2 / 1>&2）以等長空白抹除，避免誤判為檔案重導。
    for tok in REDIR_MERGE_TOKENS:
        start = 0
        while True:
            j = masked.find(tok, start)
            if j == -1:
                break
            masked = masked[:j] + (" " * len(tok)) + masked[j + len(tok):]
            start = j + len(tok)
    if "<" in masked:
        return None  # input redirect 一律不放行

    safe_roots = [Path("/tmp")]
    if WORKTREES_DIR is not None:
        safe_roots.append(WORKTREES_DIR)

    clean = remainder
    leftover = masked
    for m in re.finditer(r"([12]?>>?)\s*(\S+)", masked):
        target = m.group(2)
        tpath = resolve_token_as_path(target, effective_cwd)
        if tpath != Path("/dev/null") and not any(
                tpath == root or is_under(tpath, root) for root in safe_roots):
            return None  # 重導目標不在安全可寫路徑（/dev/null 例外：通用丟棄）
        s, e = m.start(), m.end()
        clean = clean[:s] + (" " * (e - s)) + clean[e:]
        leftover = leftover[:s] + (" " * (e - s)) + leftover[e:]
    if ">" in leftover:
        return None  # 還有未被辨識 / 驗證的輸出重導
    return clean


def strip_leading_cd(command: str, base_cwd: Path):
    """若命令以 `cd <dir> (&&|;|換行)` 開頭，剝離並回傳 (remainder, cd_target)；
    沒有前綴 cd 則回傳 (command, None)（即使後面有 ;/&& 串接也不在此拒絕，交由分段驗證）；
    cd 格式不符（多參數等）回傳 None。"""
    if not re.match(r"cd(\s|$)", command.lstrip()):
        return (command, None)
    sep = find_cd_separator(command)
    if sep is None:
        return None  # 只有 cd、後面沒命令
    idx, slen = sep
    prefix = command[:idx].strip()
    rest = command[idx + slen:].lstrip()
    try:
        ptoks = shlex.split(prefix, posix=True)
    except ValueError:
        return None
    if len(ptoks) != 2 or ptoks[0] != "cd":
        return None
    return (rest, resolve_token_as_path(ptoks[1], base_cwd))


# grep 作為管線過濾器：唯讀、無 exec / 寫檔。擋會讀任意檔的旗標與額外檔案運算元，
# 只允許單一 pattern 運算元（數字運算元視為 -A/-B/-C/-m 的旗標參數，不計入）。
GREP_FILE_FLAG_LETTERS = set("frRd")  # -f 讀 pattern 檔、-r/-R 遞迴、-d 目錄處理
GREP_BANNED_LONG = {
    "--file", "--recursive", "--dereference-recursive", "--directories",
    "--include", "--include-dir", "--exclude", "--exclude-dir", "--exclude-from",
}


def is_safe_grep_segment(segment: str) -> bool:
    try:
        tokens = drop_redir_tokens(shlex.split(segment, posix=True))
    except ValueError:
        return False
    if not tokens or tokens[0] != "grep":
        return False
    text_operands = 0
    for t in tokens[1:]:
        if t.startswith("--"):
            if t.split("=", 1)[0] in GREP_BANNED_LONG:
                return False
            continue
        if t.startswith("-") and len(t) > 1:
            if any(ch in GREP_FILE_FLAG_LETTERS for ch in t[1:]):
                return False
            continue
        if FILTER_NUM_OPERAND.match(t):
            continue  # -A/-B/-C/-m 的數字參數
        text_operands += 1
    return text_operands <= 1  # 只允許單一 pattern；>1 → 可能含檔案運算元


# 真唯讀 git 動詞（不含 branch/remote/tag/config 等帶參數會改狀態者）。
READONLY_GIT_VERBS = {
    "log", "show", "diff", "status", "ls-tree", "ls-remote", "ls-files",
    "rev-parse", "rev-list", "describe", "shortlog", "blame", "reflog",
    "cat-file", "whatchanged", "name-rev", "merge-base", "grep",
    "for-each-ref", "symbolic-ref", "fetch", "ls-remote",
}
# 唯讀 git 動詞底下仍能寫檔 / 執行外部程式的旗標一律擋。
BANNED_GIT_ARGS = {"-O", "--open-files-in-pager", "--output", "--ext-diff"}
# git 動詞前可安全略過的全域選項（無 exec / 不改 dir / 不指向別的 repo）。其餘任何
# `-` 開頭全域選項（-c 注入、-C/--git-dir/--work-tree 改 dir/repo、--exec-path 等）一律不放行。
GIT_SAFE_GLOBAL_OPTS = {
    "--no-pager", "-p", "--paginate", "--no-replace-objects", "--no-optional-locks",
    "--literal-pathspecs", "--icase-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
}


# 純字串 / 不讀檔的安全頭（運算元是字串，非路徑）。
STRING_SAFE_HEADS = {"echo", "printf", "pwd", "true", "false", "dirname", "basename"}
# 讀檔案內容 / 中繼資料的安全頭（檔案運算元須在 ws/tmp 內）。
READ_FILE_HEADS = set(SAFE_FILTERS) | {"ls", "stat", "file", "realpath", "readlink"}
# find 有副作用的 action（執行 / 刪除 / 寫檔）一律擋；其餘 -path/-name/-type/-o… 唯讀。
FIND_BANNED_ACTIONS = {
    "-exec", "-execdir", "-ok", "-okdir", "-delete",
    "-fprintf", "-fprint", "-fprint0", "-fls", "-files0-from",
}


def _read_path_ok(token: str, cwd: Path) -> bool:
    """檔案/目錄運算元解析後須落在 workspace 或 /tmp 內（擋 ~/.aws、/etc 等盒外讀取）。
    旗標（- 開頭）放行；pattern 等非真實外部路徑會解析到 cwd 底下→在 workspace 內→放行。"""
    if token.startswith("-"):
        return True
    p = resolve_token_as_path(token, cwd)
    roots = [Path("/tmp")]
    if EXPECTED_CWD is not None:
        roots.append(EXPECTED_CWD)
    return any(p == r or is_under(p, r) for r in roots)


def is_read_head(head_tokens: list[str], cwd: Path) -> bool:
    """cat/head/tail/wc/nl/ls/stat… + 檔案運算元（ws/tmp 內），或純字串頭 echo/pwd…，
    或 grep 搜尋（pattern + 路徑 ws/tmp 內，擋 -f 從檔讀 pattern）。唯讀、盒內外皆安全。"""
    h = head_tokens[0]
    if h in STRING_SAFE_HEADS:
        return True
    if h == "grep":
        seen_pattern = False
        for t in head_tokens[1:]:
            if t.startswith("--"):
                if t == "--file" or t.startswith("--file="):
                    return False
                continue
            if t.startswith("-") and len(t) > 1:
                if "f" in t[1:]:  # -f 或夾帶 f 的短旗標叢集：從檔讀 pattern → 擋
                    return False
                continue
            if not seen_pattern:
                seen_pattern = True  # 第一個非旗標是 pattern，不當路徑檢查
                continue
            if not _read_path_ok(t, cwd):
                return False
        return seen_pattern
    if h in READ_FILE_HEADS:
        for t in head_tokens[1:]:
            if t in BANNED_FILTER_FLAGS:
                return False
            if not _read_path_ok(t, cwd):
                return False
        return True
    return False


def is_explore_head(head_tokens: list[str], cwd: Path) -> bool:
    """沙箱內才放行的段型（純鏈、不得在含 trusted/git 的盒外鏈出現），由沙箱關住其效果：
    - 任意 python 直譯（含 -c / 腳本檔 / -m）：與既有 `Bash(python3:*)` 一致，效果靠沙箱框住。
    - find：擋有副作用的 action（-exec/-delete/-fprintf…），起點路徑限 ws/tmp。"""
    h = head_tokens[0]
    if h in ("python", "python3") or re.match(r"^python3\.\d+$", h):
        return True
    if h != "find":
        return False
    for t in head_tokens[1:]:
        if t in FIND_BANNED_ACTIONS:
            return False
    for t in head_tokens[1:]:
        if t.startswith("-") or t in ("(", ")", "!"):
            break  # 進入 expression，後面是 -name/-path 等述語，非起點路徑
        if not _read_path_ok(t, cwd):
            return False
    return True


def classify_head(head_tokens: list[str], effective_cwd: Path):
    """單一指令頭（無 pipe）分類：'trusted'/'git'/'read'/'explore'/None。"""
    # trusted-script。
    script_path = find_script_path(head_tokens, effective_cwd)
    if (script_path is not None and script_path.exists()
            and script_path.is_file() and is_under(script_path, TRUSTED_SCRIPT_DIR)):
        return "trusted"
    # 唯讀 git：git [安全全域選項]* <唯讀動詞> [參數]；擋注入(-c/-C/--git-dir…)與寫檔/exec 旗標。
    if head_tokens[0] == "git":
        i = 1
        while i < len(head_tokens) and head_tokens[i] in GIT_SAFE_GLOBAL_OPTS:
            i += 1
        if (i < len(head_tokens) and not head_tokens[i].startswith("-")
                and head_tokens[i] in READONLY_GIT_VERBS):
            for t in head_tokens[i + 1:]:
                if t in BANNED_GIT_ARGS or t.startswith("--output=") or t.startswith("-O"):
                    return None
            return "git"
    # 安全讀取（檔案運算元限 ws/tmp）：cat/head/tail/wc/nl/ls/stat/grep搜/echo…
    if is_read_head(head_tokens, effective_cwd):
        return "read"
    # 探索（find/python；僅純鏈、沙箱內放行）。
    if is_explore_head(head_tokens, effective_cwd):
        return "explore"
    return None


def classify_segment(seg: str, effective_cwd: Path):
    """驗證單一 segment（已無 top-level ;/&&、安全輸出重導已抽掉）。回傳段型或 None。
    每個 pipe 段都用 classify_head 同一套規則分類；explore（python/find，效果靠沙箱關住）
    不得與 trusted/git（會把整條帶到沙箱外）同處一條管線。"""
    masked = strip_quoted(seg)
    masked_nm = masked
    for tok in REDIR_MERGE_TOKENS:
        masked_nm = masked_nm.replace(tok, " ")
    # 殘留重導（未被抽掉＝不安全）、背景化、換行一律不放行。
    if ">" in masked_nm or "<" in masked_nm:
        return None
    if "&" in masked_nm or "\n" in masked_nm:
        return None

    parts = split_top_level_pipe(seg)
    if any(not p.strip() for p in parts):
        return None  # `||` / 前後懸空 pipe

    kinds = []
    for p in parts:
        try:
            ht = drop_redir_tokens(shlex.split(p, posix=True))
        except ValueError:
            return None
        if not ht:
            return None
        k = classify_head(ht, effective_cwd)
        if k is None:
            return None  # 任一管線段不是安全形式 → 整段退回
        kinds.append(k)

    has_anchor = any(k in ("trusted", "git") for k in kinds)
    has_explore = any(k == "explore" for k in kinds)
    if has_anchor and has_explore:
        return None  # python/find 不得與 trusted/git 同管線（後者會跑到沙箱外）
    if has_anchor:
        return "trusted" if "trusted" in kinds else "git"
    if has_explore:
        return "explore"
    return "read"


# 會被 excludedCommands 帶到沙箱「外」執行的工具（其餘指令留在沙箱內、被沙箱圍堵）。
EXCLUDED_TOOL_RE = re.compile(r"(?<![\w./-])(kubectl|gh|docker|helm|argocd)(?![\w./-])")
# 只有「網路 git」（push/fetch/pull/clone/ls-remote）跑到沙箱外；本機 git 留沙箱內由其圍堵。
GIT_NETWORK_RE = re.compile(
    r"(?<![\w./-])git(?:\s+-{1,2}[^\s]+)*\s+(push|fetch|pull|clone|ls-remote)(?![\w./-])")


def contains_excluded_tool(remainder: str) -> bool:
    """remainder（strip_quoted 後）含任何會跑到沙箱外的工具（kubectl/gh/docker/helm/argocd、
    網路 git push/fetch/…、trusted-script 路徑）→ True，需嚴格逐段驗證；否則整條留沙箱內，
    可廣義放行（本機 git log/status/branch/commit 等與 for 迴圈/python 串接也整條留沙箱內）。
    對齊性：clean `git push` 同時被此處與 excludedCommands `git push*` 命中→盒外+嚴格擋(§2.2)；
    混淆形式兩邊都漏→落沙箱內無網路而 push 失敗→無外洩。"""
    bare = strip_quoted(remainder)
    return (bool(EXCLUDED_TOOL_RE.search(bare)) or bool(GIT_NETWORK_RE.search(bare))
            or "approved-scripts/allow/" in bare)


def evaluate_trusted(command: str, payload_cwd: Path) -> bool:
    """放行判斷。可選 `cd <workspace 或 /tmp 下任一目錄>` 前綴。

    嚴格逐段驗證：trusted-script / 唯讀 git / 安全讀取（路徑限 ws/tmp）自動放行。
    explore（python/find）一律 no_decision：沙箱可能被 dangerouslyDisableSandbox 繞過，
    hook 無從得知，交回 Claude Code 決定（沙箱開啟時由 autoAllowBashIfSandboxed 接手）。
    背景化 & / nohup 等已於 main 的 detached 階段 deny。"""
    stripped = strip_leading_cd(command, payload_cwd)
    if stripped is None:
        return False
    remainder, cd_target = stripped

    effective_cwd = cd_target if cd_target is not None else payload_cwd
    if EXPECTED_CWD is None or effective_cwd is None:
        return False
    tmp = Path("/tmp")
    if not (effective_cwd == EXPECTED_CWD or is_under(effective_cwd, EXPECTED_CWD)
            or effective_cwd == tmp or is_under(effective_cwd, tmp)):
        return False  # cd 目標 / 執行 cwd 必須在 workspace 或 /tmp 範圍內

    # 嚴格路徑（B 路線已移除：沙箱可能被 dangerouslyDisableSandbox 繞過，hook 無從得知）。
    # 展開語法一律不放行（雙引號內的 $()/反引號也算）；涵蓋所有 segment。
    if has_active_expansion(remainder):
        return False
    # 放行輸出重導到安全可寫路徑（/tmp、<workspace>/.worktrees）；抽掉並驗證目標後再分段。
    redir_clean = extract_output_redirects(remainder, effective_cwd)
    if redir_clean is None:
        return False

    # 以 top-level ;/&& 分段；每段須獨立為安全形式。
    chain = split_top_level_and_list(redir_clean)
    if any(not seg.strip() for seg in chain):
        return False
    kinds = []
    for seg in chain:
        kind = classify_segment(seg, effective_cwd)
        if kind is None:
            return False
        kinds.append(kind)
    # 含 trusted/git 的鏈會被 excludedCommands 帶到沙箱外執行 → 只准 trusted/git/read，
    # 不准 explore（find 不得在沙箱外跑，避免其 blocklist 萬一有漏時失去沙箱兜底）。
    if any(k in ("trusted", "git") for k in kinds):
        return all(k in ("trusted", "git", "read") for k in kinds)
    # explore（python/find）沙箱可能被繞過，不在此自動放行；純讀取（路徑限 ws/tmp）不依賴沙箱。
    return all(k == "read" for k in kinds)


def evaluate_worktree_git(command: str, payload_cwd: Path) -> bool:
    """safety-net.md §2.1：git add / commit 只在 .worktrees/ 下 allow。

    接受可選的 `cd <.worktrees 下目錄>` 前綴，主體須為一個或多個以 `&&` / `;`
    串接、且每段都是 `git add` 或 `git commit` 的命令（不接 pipe / 重導 / 展開 /
    背景化）；effective cwd 必須落在 <workspace>/.worktrees/ 底下。
    """
    if WORKTREES_DIR is None:
        return False

    # 展開語法一律不放行（雙引號內的 $()/反引號也算）。
    if has_active_expansion(command):
        return False

    remainder = command
    effective_cwd = payload_cwd

    # 可選的前綴 cd —— 只有命令本身以 `cd` 開頭時才剝離。
    if re.match(r"cd(\s|$)", command.lstrip()):
        sep = find_cd_separator(command)
        if sep is None:
            return False  # 只有 cd、後面沒有 git
        idx, slen = sep
        prefix = command[:idx].strip()
        try:
            ptoks = shlex.split(prefix, posix=True)
        except ValueError:
            return False
        if len(ptoks) != 2 or ptoks[0] != "cd":
            return False
        effective_cwd = resolve_token_as_path(ptoks[1], payload_cwd)
        remainder = command[idx + slen:].lstrip()

    if not is_under(effective_cwd, WORKTREES_DIR):
        return False

    masked = strip_quoted(remainder)
    masked_no_redir = masked
    for tok in REDIR_MERGE_TOKENS:
        masked_no_redir = masked_no_redir.replace(tok, " ")
    # git add/commit 不需要 pipe / 寫檔重導 / 額外換行；背景化 & 已在 detached 階段擋掉。
    if any(c in masked_no_redir for c in (">", "<", "|", "\n")):
        return False

    # 主體可為一個或多個以 && / ; 串接、且每段都是 git add / commit 的命令。
    segments = split_top_level_and_list(remainder)
    if any(not seg.strip() for seg in segments):
        return False

    for seg in segments:
        try:
            toks = drop_redir_tokens(shlex.split(seg, posix=True))
        except ValueError:
            return False
        if len(toks) < 2 or toks[0] != "git" or toks[1] not in ("add", "commit"):
            return False

    return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return no_decision()

    if payload.get("hook_event_name") != "PreToolUse":
        return no_decision()
    if payload.get("tool_name") != "Bash":
        return no_decision()

    cwd = Path(payload.get("cwd") or ".").expanduser().resolve()
    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") or ""
    if not isinstance(command, str) or not command.strip():
        return no_decision()

    command = normalize_command(command)

    # 1) forbidden：未受控 detached 服務一律 deny（先於 allow，且不受 cwd 限制）。
    reason = detached_service_reason(command)
    if reason is not None:
        return emit("deny", reason)

    # 2) allow：trusted script（含安全的 cd 前綴 / redirect 合併 / 純輸出過濾 pipe）。
    if evaluate_trusted(command, cwd):
        return emit("allow", "approved-scripts/allow trusted script（safety-net.md §2.1）。")

    # 3) allow：.worktrees/ 下的 git add / commit（safety-net.md §1 / §2.1）。
    if evaluate_worktree_git(command, cwd):
        return emit("allow", ".worktrees/ 內 git add / commit（safety-net.md §2.1）。")

    return no_decision()


if __name__ == "__main__":
    raise SystemExit(main())
