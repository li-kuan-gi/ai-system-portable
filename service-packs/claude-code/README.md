# Claude Code Service Pack

本 pack 說明如何讓 Claude Code 消費 portable core。

依 Claude Code 官方文件，幾個穩定入口是：

- `CLAUDE.md` 或 `.claude/CLAUDE.md`：project memory / agent instructions
- `.claude/settings.json`：可 commit 的 project settings
- `.claude/settings.local.json`：不應 commit 的 local settings
- `.claude/skills/<skill-name>/SKILL.md`：project skills
- `.claude/commands/`：既有 custom commands 仍可用，但 skills 是建議方向
- Claude Code hooks：定義在 settings JSON 內，用來在工具事件前後執行檢查或提醒

## 本 pack 提供

```text
templates/
  CLAUDE.md
  .claude/settings.json
  .claude/skills/portable-entry/SKILL.md
  .claude/hooks/README.md
```

## 導入方式

1. 將 portable core 放到 workspace root。
2. 將 `templates/CLAUDE.md` 複製到 workspace root 的 `CLAUDE.md`，或合併到既有 `CLAUDE.md`。
3. 將 `templates/.claude/settings.json` 合併到 `.claude/settings.json`。
4. 若要讓 Claude Code 以 skill 方式顯式讀 portable entry，可複製 `templates/.claude/skills/portable-entry/`。
5. 任何 local-only 設定放在 `.claude/settings.local.json`，不要 commit。

## 與 Portable Core 的關係

Claude Code 的 `CLAUDE.md` 只負責把 Claude 導向 portable core：

```text
ai-system/entry.md -> ai-system/rules.md -> ai-system/skills/README.md
```

不要把 portable core 的完整規則複製進 `CLAUDE.md`，避免雙軌維護。

## 權限與安全網

Claude Code 的 `.claude/settings.json` 可設定 `permissions.allow` / `permissions.deny`。本 pack 只提供保守模板：

- deny 常見 secret / env 檔讀取
- 不預設 allow 任何 destructive command
- 不把 `ai-system/approved-scripts/allow` 自動映射成 allow，除非你另行實作並驗證 hook

若要實作「trusted approved script」自動放行，建議新增 Claude Code 專用 hook。不要直接沿用 Codex hook，因為兩者 hook event payload 和 decision semantics 不同。

## 參考

- Claude Code settings：`https://code.claude.com/docs/en/settings`
- Claude Code skills / slash commands：`https://code.claude.com/docs/en/slash-commands`
- Claude Code hooks：`https://code.claude.com/docs/en/hooks`
