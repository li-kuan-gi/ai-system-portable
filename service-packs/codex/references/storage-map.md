# Codex Storage Map

本文件說明 Codex / OpenAI Codex CLI 在 `CODEX_HOME` 下常見的 service-managed storage 位置。這些路徑是給 agent 查找脈絡與設定用，不是 portable core 內容，也不應被整包複製。

`CODEX_HOME` 預設通常是 `~/.codex`，但 portable 導入應以實際 launcher 設定為準。

## Agent 可讀入口

| 類型 | 常見路徑 | 用途 | 讀取邊界 |
|---|---|---|---|
| 設定 | `<CODEX_HOME>/config.toml` | Codex 設定、hook / workspace 設定來源 | 可在任務需要確認 runtime 設定時讀取；不要自動改寫 |
| 對話 sessions | `<CODEX_HOME>/sessions/` | Codex session / rollout jsonl 紀錄 | 只在需要延續歷史脈絡或查證對話時讀取；優先摘要，不搬 raw transcript |
| 歷史索引 | `<CODEX_HOME>/history.jsonl` | prompt / history 類紀錄 | 只在需要找歷史脈絡時讀取；注意可能含使用者輸入 |
| memories | `<CODEX_HOME>/memories/` | Codex memory workspace 或持久化記憶 | 可查 agent 記憶來源；不得把 secret 寫入 memory |
| hooks | `<CODEX_HOME>/hooks/` | Permission hook 等本機實作 | 可查安全網實作；修改仍需符合安全網契約 |
| rules | `<CODEX_HOME>/rules/` | Codex rules profile | 可查實際 profile；portable core source of truth 仍在 workspace `ai-system/` |
| log | `<CODEX_HOME>/log/`、`<CODEX_HOME>/logs_*.sqlite` | runtime log / diagnostics | 只在 debug Codex runtime 時讀取；避免把大量 log 貼進治理文件 |
| state / cache | `<CODEX_HOME>/state_*.sqlite`、`cache/`、`tmp/` | runtime state、cache、暫存資料 | 不視為制度或知識來源；通常不需要讀 |
| shell snapshots | `<CODEX_HOME>/shell_snapshots/` | shell snapshot / command context | 只在需要重建執行脈絡時讀取 |

## 禁止讀取或複製的敏感位置

| 類型 | 常見路徑 | 規則 |
|---|---|---|
| auth | `<CODEX_HOME>/auth.json` | 不讀、不複製、不摘要 |
| secrets | `<CODEX_HOME>/secrets/` | 不讀、不複製、不摘要 |

若任務需要確認 auth / secret 是否存在，只能查路徑存在與權限狀態，不得讀取內容。

## 導入時的記錄方式

`scripts/install-codex-portable.sh --apply` 會把實際 `CODEX_HOME` 對應的 storage map 寫入目標 workspace：

```text
ai-system/knowledge/context/agent-settings.md
```

後續 agent 應先讀該 workspace 的 `agent-settings.md`，再依任務需要讀取 Codex service-managed storage。
