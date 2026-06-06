# 可攜邊界

## 可放入 Portable Core 的內容

- `ai-system/entry.md` agent 日常入口契約，且不綁定特定 AI 服務
- `ai-system/governance/contracts.md` 制度 / 知識 / 安全網責任模型
- 最小行為規則與高回頭成本 gate
- 治理原則與制度修改判準
- 通用行為限制細則
- 安全網契約與 approved script 分類
- workspace skill index 架構
- 制度審計與知識治理 skills
- append-only patchlog 與 friction notes
- 初始化的 agent-readable history / settings context 模板
- approved script 目錄分類
- 紀錄追加與受控 git worktree 的通用 helper
- AI service adapter / implementation pack 的分層規則

## 必須留在 Instance Adapter 的內容

- 產品、客戶、公司或 domain-specific 工作流
- 環境 catalog、namespace、host、deploy target、dashboard、database
- 憑證、本機 secret 檔案與 credential lookup recipe
- 綁定特定 issue tracker、log platform、cloud、Kubernetes、CI、release 或 API 的 helper
- 其他 workspace 的 patchlog / friction notes 歷史紀錄
- 實際已導入的 user-level safety-net config、auth、session、cache 或 log
- Codex、Claude Code 或其他 AI 服務的 user-level 私有狀態

## Adapter 形狀

Instance adapter 可以新增：

```text
ai-system/
  skills/<workspace-task>/SKILL.md
  skills/<workspace-task>/references/
  knowledge/context/
  knowledge/domains/
  approved-scripts/allow/<instance-helper>
  approved-scripts/prompt/<instance-helper>
```

Adapter 檔案不應改變 portable core 契約，除非該變更離開目前 workspace 也仍然有用。

## Service Pack 形狀

特定 AI 服務的方便工具與設定放在 `service-packs/<service>/` 或 `implementation-packs/<runtime>/`。

可包含：

- 該服務的入口檔模板，例如 `CLAUDE.md` 或同等 manifest
- 該服務的 project settings 範本
- 該服務的 skill / command bridge
- 該服務的 hook / permission / sandbox 實作範例
- 安裝或合併說明

不可包含：

- auth / session / cache / log
- secret、token、password、cookie、bearer
- 綁定原 workspace 的絕對路徑
- 使用者私有狀態

原則：service pack 只讓某個 AI 服務更容易消費 portable core，不得把 core 改成該服務專屬。

## 驗證清單

導入其他地方前：

1. 先用 `scripts/install-portable-system.sh --target-root <WORKSPACE_ROOT> --dry-run` 檢查會安裝哪些檔案。
2. 搜尋舊 workspace 名稱、產品名、host、客戶名與工具特定憑證。
3. 檢查檔名與目錄名，確認 root 下沒有 instance-like 目錄、舊 repo 名稱或 hidden service-specific skill 目錄。
4. 確認 `ai-system/skills/README.md` 的每個入口都指向存在的 `SKILL.md`。
5. 對 `ai-system/approved-scripts/allow/*` 與 `prompt/*` 跑 shell syntax check。
6. 對 `ai-system/approved-scripts/_lib/*.py` 跑 Python syntax check。
7. 跑 `patchlog-append --dry-run` 與 `friction-notes-append --dry-run`。
8. 確認 package 內沒有 secret。
9. 確認 `governance/patchlog.md`、`governance/friction_notes.md`、`knowledge/context/agent-history.md` 與 `knowledge/context/agent-settings.md` 仍是初始化狀態，未混入來源 workspace 的歷史內容。

若要為 Codex 一次安裝制度與固定啟動 command，先用 `scripts/install-codex-portable.sh --target-root <WORKSPACE_ROOT> --codex-home <CODEX_HOME> --command-name <COMMAND> --shell-rc <RC> --dry-run` 檢查會寫入哪裡。若刻意不安裝 shell rc alias，`--apply` 時必須互動確認或傳入 `--confirm-no-shell-rc`。若需要讓新 workspace agent 看到既有歷史對話摘要或設定，使用 `--agent-history-file` / `--agent-settings-file` 匯入已整理且不含 secret 的 markdown。

在 portable package root 可用下列命令重跑第 2 點；應無輸出。此檢查以 portable package root allowlist 為準；任何不在 allowlist 的 package-owned root entry 都會被列出。

```sh
ai-system/approved-scripts/allow/portable-boundary-scan --root .
```

若要額外檢查導出來源的舊 repo / workspace prefix，可重複傳入：

```sh
ai-system/approved-scripts/allow/portable-boundary-scan --root . \
  --reject-prefix <old-prefix>
```

若目前 AI runtime 將 `.agents`、`.codex` 或同等服務目錄以 read-only mount point 掛在 package root，這不是 portable package 內容；發布、複製或打包時仍必須排除這些 mount point，不得把它們收進成品。
