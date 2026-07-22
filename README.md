# 可攜 Agent 制度

這是一套不綁定特定公司、產品或環境的 agent 制度核心。核心契約保持
AI 服務中性；可選工具整合可以支援具名服務，但不得攜帶私有狀態或
instance 假設。

## GitHub 發布狀態

本 package 目標是可公開發布、可複製、可導入不同 workspace 的 portable core。公開前應確認：

- `ai-system/knowledge/context/agent-history.md` 與 `agent-settings.md` 維持初始化狀態，沒有私人歷史或本機設定。
- package 內沒有 auth、session、cache、log、secret、token、password、cookie、bearer 或 credential 值。
- package 內沒有特定公司、客戶、產品、host、namespace、部署目標或 workspace 專屬工作流。
- `PORTABILITY.md` 的驗證清單已重跑，且 `portable-boundary-scan` 沒有列出異常 root entry。

本 repository 以 MIT License 發布，見 `LICENSE`。

它提供：

- 服務中性的 agent 日常入口
- 制度 / 知識 / 安全網的上位契約
- 制度演化的治理原則
- 邊界模糊或高風險操作的行為細則
- workspace skill 路由
- 初始化的 append-only 治理紀錄
- agent 可讀的歷史對話與設定模板
- approved script 目錄結構、少量通用 helper 與可選工具整合
- 不同 AI 服務的 adapter / implementation pack 邊界

它刻意不包含特定 instance 的環境、憑證、業務 domain、account、target、部署流程或產品工作流。那些內容應放在各 workspace 自己的 adapter layer。

## 核心模型

portable core 以三種責任分工：

| 責任 | 角色 | 主要落點 |
|---|---|---|
| 制度 | 控制面：目標、判準、停下 gate、變更規則 | `ai-system/rules.md`、`constraints-detail.md`、`governance/` |
| 知識 | 事實面：制度知識、安全網知識、知識系統知識與任務知識 | `ai-system/knowledge/` |
| 安全網 | 執行面：sandbox、hook、permission、approved scripts、機械式保護 | `ai-system/safety-net.md`、`approved-scripts/`、`implementation-packs/` |

完整契約見 `ai-system/governance/contracts.md`。

## 分層

| 層級 | 用途 | 例子 |
|---|---|---|
| 可攜核心 | 穩定入口、責任契約、規則、gate、治理原則與通用 helper | `entry.md`、`rules.md`、`constraints-detail.md`、`safety-net.md`、`governance/contracts.md`、`governance/principles.md` |
| Workspace skills | 任務路由與可重複工作流入口 | `ai-system/skills/*/SKILL.md` |
| Knowledge | 已驗證事實、制度 / 安全網 / 知識系統脈絡與任務知識 | `ai-system/knowledge/` |
| Safety net | 機械式保護契約與可審查 executable 入口 | `ai-system/safety-net.md`、`ai-system/approved-scripts/allow/`、`prompt/` |
| Instance adapter | 特定公司 / 產品 / account / target / 環境內容 | 自訂 skills、knowledge、scripts、secrets |
| Service pack | 特定 AI 服務的入口、設定、hook / permission 實作 | `service-packs/`、`implementation-packs/` |

## 導入檢查

Codex 使用者建議先用高層導入腳本 dry-run；它會安裝制度、Codex safety-net files，並產生固定啟動 command：

```sh
scripts/install-codex-portable.sh \
  --target-root <WORKSPACE_ROOT> \
  --codex-home <CODEX_HOME> \
  --command-name codex-my-workspace \
  --bin-dir "$HOME/.local/bin" \
  --shell-rc "$HOME/.bashrc" \
  --dry-run
```

確認後改用 `--apply`。此腳本會自動尋找 `codex` binary；若找不到，會停止並提示先安裝 Codex CLI，或改用 `--codex-bin <path>` 指定。它會同步安裝 Codex safety-net `config.toml`：目標不存在時直接建立，已存在且未知時要求 `--backup-existing` 或人工合併。若沒有提供 `--shell-rc`，`--apply` 會要求明確確認；非互動環境可用 `--confirm-no-shell-rc` 表示刻意不安裝 shell alias。

若已有整理好的歷史對話摘要或設定，可加上：

```sh
  --agent-history-file <HISTORY_MD> \
  --agent-settings-file <SETTINGS_MD>
```

這兩個檔案會被放到 `ai-system/knowledge/context/agent-history.md` 與 `agent-settings.md`。Codex 一步導入腳本也會把產生的 launcher command、`CODEX_HOME`、resolved config snippet 位置，以及 Codex 對話 sessions、history、memory、log、auth / secrets 等 service-managed storage 路徑追加到 `agent-settings.md`；敏感路徑只記位置，不讀取內容。

若只要安裝 portable core，建議先 dry-run：

```sh
scripts/install-portable-system.sh \
  --target-root <WORKSPACE_ROOT> \
  --codex-home <CODEX_HOME> \
  --dry-run
```

確認後再安裝：

```sh
scripts/install-portable-system.sh \
  --target-root <WORKSPACE_ROOT> \
  --codex-home <CODEX_HOME> \
  --apply
```

若目標已存在 `AGENTS.md`、`ai-system/` 或 Codex hook / rules / config snippet，預設會拒絕覆寫。確認要更新時，先 dry-run，再使用 `--backup-existing`。

`--backup-existing` 會把既有 core 搬到 `<WORKSPACE_ROOT>.ai-system-install-backups/`，避免在目標 root 內留下額外 package entry；Codex hook / rules / config snippet 的備份仍放在指定 `CODEX_HOME` 下。

Codex 專用啟動指令：

```sh
scripts/start-codex.sh \
  --workspace <WORKSPACE_ROOT> \
  --codex-home <CODEX_HOME> \
  --codex-bin <CODEX_BINARY>
```

此指令會從 workspace root 啟動 Codex，並以指定 `CODEX_HOME` 作為 Codex user home；它會檢查制度入口與 Codex safety-net 檔案是否存在，但不會修改 `config.toml`。

若只要產生固定命令，例如 `codex-my-workspace`：

```sh
scripts/install-codex-command.sh \
  --workspace <WORKSPACE_ROOT> \
  --codex-home <CODEX_HOME> \
  --command-name codex-my-workspace \
  --bin-dir "$HOME/.local/bin" \
  --shell-rc "$HOME/.bashrc" \
  --dry-run
```

確認後改用 `--apply`。產生的 command 會把 workspace、`CODEX_HOME` 與 Codex binary 寫入 wrapper，之後直接執行該 command 即可啟動；若使用 `--shell-rc` 追加 alias，需重新開 shell 或 `source` 該 rc 檔。

導入後：

1. 讓目標 AI 服務的入口檔指向 `ai-system/entry.md`。
2. 依目標 workspace 替換或新增任務 skills。
3. 特定 instance 的 helper 只能透過 `ai-system/approved-scripts/allow/` 或 `prompt/` 增加。
4. secrets 預設留在 workspace 外，除非有明確 local-only 規則允許。
5. 依 `PORTABILITY.md` 的驗證清單檢查。

## Claude Code 導入

Claude Code 使用者可用一步導入腳本，先 dry-run：

```sh
scripts/install-claude-portable.sh \
  --target-root <WORKSPACE_ROOT> \
  --dry-run
```

確認後改用 `--apply`。它會一次安裝 portable core、`CLAUDE.md` 入口，以及 Claude safety-net（PreToolUse permission hooks + `settings.json` + sandbox 圍堵）到 `<WORKSPACE_ROOT>/.claude`。若目標已存在對應檔案，預設拒絕覆寫；確認要更新時先 dry-run，再使用 `--backup-existing`。

只要安裝安全網（已有 portable core 與 `CLAUDE.md`）時：

```sh
implementation-packs/claude-safety-net/scripts/install-safety-net.sh \
  --workspace <WORKSPACE_ROOT> \
  --dry-run
```

安裝後可跑回歸 probe 驗證 hook：

```sh
python3 implementation-packs/claude-safety-net/scripts/probe-hook.py
```

若目標 workspace 使用 kubectl / helm / argocd，再把 `implementation-packs/claude-safety-net/templates/settings.devops-readonly.example.json` 合併進 `.claude/settings.json`。（git 與 gh 已在中性預設內。）

## AI 服務分層

Portable core 只定義制度契約，不假設使用 Codex、Claude Code 或其他服務。

Portable core 可以提供跨公司的可選整合，例如讀取 Claude Code／Codex
session 格式的 workspace-scoped helper；實際 session、auth、cache 與 log
仍由服務管理，絕不納入 package。

- Codex / OpenAI Codex CLI 相關安全網範例在 `implementation-packs/codex-safety-net/` 與 `service-packs/codex/`。
- Claude Code 入口模板在 `service-packs/claude-code/`，安全網（hooks + `settings.json`）在 `implementation-packs/claude-safety-net/`，一步安裝用 `scripts/install-claude-portable.sh`。
- 其他 AI 服務應新增自己的 `service-packs/<service>/`，只放該服務的入口、設定、permission、hook、skill bridge 或安裝說明。
