# Service Packs

本目錄放「特定 AI 服務如何消費 portable core」的 adapter。

portable core 不預設使用 Codex、Claude Code 或任何單一服務。每個 service pack 只處理該服務的：

- 入口檔模板
- project / user settings 範本
- skill / command bridge
- hook / permission / sandbox 提醒
- 安裝或合併說明

## Packs

| Pack | 用途 |
|---|---|
| `codex/` | Codex / OpenAI Codex CLI 入口與 `~/.codex` safety-net 實作索引 |
| `claude-code/` | Claude Code 的 `CLAUDE.md`、`.claude/settings.json`、skill bridge 與 hook/permission 提醒 |
| `generic/` | 給未知或尚未支援服務的最小導入契約 |

## 原則

- service pack 不得修改 portable core 的制度語意。
- service pack 不得包含 auth、secret、session、log、cache。
- service pack 使用 placeholder，不綁定原 workspace 絕對路徑。
- 若官方服務設定變動，更新 service pack，不要改 core。

