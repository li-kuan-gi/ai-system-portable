# Claude Code Entry

本 workspace 使用 service-agnostic portable agent system。

## 先讀

1. `ai-system/entry.md`

## 不要做

- 不要把 `ai-system/entry.md` 或 `ai-system/rules.md` 的內容複製到本檔形成第二份規則。
- 不要把 service-specific permission table 當成制度本體。
- 不要讀取或寫入 secrets、tokens、passwords。
- 不要把 `.claude/settings.local.json`、auth、session、log、cache 類 local state 加入版本控制。

## Claude Code 專用提醒

- 本檔只是 Claude Code 的 project memory 入口；正式制度來源仍是 `ai-system/`。
- 若需要顯式使用 portable entry skill，可呼叫 `.claude/skills/portable-entry/SKILL.md` 對應的 skill。
- 高回頭成本操作仍依 `ai-system/rules.md` 停下 gate 判斷。
