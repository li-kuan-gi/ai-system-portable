# Codex Service Pack

本 pack 說明如何讓 Codex / OpenAI Codex CLI 消費 portable core。

## 入口

Codex 主要透過 workspace root 的 `AGENTS.md` 取得入口。portable package 中的 `AGENTS.md` 只是 adapter；正式服務中性入口是 `ai-system/entry.md`。

portable package 已提供：

```text
AGENTS.md
ai-system/entry.md
ai-system/rules.md
ai-system/skills/README.md
```

## 安全網

Codex 的本機安全網實作範例放在：

```text
implementation-packs/codex-safety-net/
```

包含：

- `~/.codex/rules/minimal.rules` 範例
- optional rules profile 範例
- `~/.codex/hooks/allow_trusted_script_permission.py`
- `~/.codex/config.toml` snippet
- dry-run / apply 安裝腳本

## Storage Map

Codex 本身的設定、對話紀錄、history、memory、log 與 auth / secrets 由 Codex service 管理，常見位置整理在 `references/storage-map.md`。

這些路徑可供 agent 在需要延續脈絡或查設定時讀取，但不屬於 portable core；`auth.json` 與 `secrets/` 只能確認存在，不得讀取內容。

## 導入步驟

1. 用 `scripts/install-codex-portable.sh --target-root <WORKSPACE_ROOT> --codex-home <CODEX_HOME> --command-name <COMMAND> --shell-rc <RC> --dry-run` 檢查導入內容；若有歷史摘要或設定檔，加上 `--agent-history-file <HISTORY_MD>` / `--agent-settings-file <SETTINGS_MD>`。
2. 確認後改用 `--apply` 安裝 portable core、Codex safety-net files、`config.toml` 與固定啟動 command。
3. 若 `<CODEX_HOME>/config.toml` 已存在且有未知內容，安裝器會停止；使用 `--backup-existing` 可備份後以 resolved config 取代，或自行合併 `<CODEX_HOME>/templates/portable-codex-safety-net.config.resolved.toml`。
4. 之後直接執行該 command，或用 `scripts/start-codex.sh --workspace <WORKSPACE_ROOT> --codex-home <CODEX_HOME>` 從固定 workspace root 啟動 Codex。
5. 不複製任何 `~/.codex/auth.json`、`~/.codex/secrets/`、sessions、logs 或 cache。

## Service-Specific 注意事項

- Codex execution layer 可以透過 PermissionRequest hook 消費 `ai-system/approved-scripts/allow`。
- `ai-system/approved-scripts/allow` 是制度授權 source of truth；`~/.codex` 只是實作層。
- `scripts/install-codex-portable.sh` 是 Codex 導入的一步入口：安裝制度、安裝 Codex safety-net files、尋找 Codex binary，並產生固定 command；它會把產生的非敏感 launcher 設定與 Codex storage map 寫入 `ai-system/knowledge/context/agent-settings.md`。
- `scripts/install-codex-command.sh` 會產生一個固定 command wrapper，可選擇追加 alias 到 shell rc；alias 需重新開 shell 或 source 該 rc 檔後才會生效。
- `scripts/start-codex.sh` 只負責以指定 workspace / CODEX_HOME 啟動 Codex；不會修改 `config.toml` 或安裝 secret。
- 若同一 workspace 也支援 Claude Code 或其他服務，不要把 Codex-only 設定寫進 `rules.md`。
