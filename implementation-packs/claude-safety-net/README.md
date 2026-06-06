# Claude Code Safety-Net Implementation Pack

本 pack 是 portable core 的一個 **Claude Code execution layer 實作範例**。

它很有用，但不是制度核心。portable core 定義「應該有安全網與 approved-scripts 契約」；本 pack 示範如何在 workspace 的 `.claude/` 內落地：

- PreToolUse permission hook：自動 allow trusted approved script 與 `.worktrees/` 內編輯
- forbidden 機械攔截：未受控 detached / 長時間常駐服務一律 deny
- 可 commit 的 `settings.json` permission + sandbox 範本
- sandbox 圍堵（filesystem denyWrite / allowWrite、denyRead 憑證、無網路預設）

正式安全網契約見 `ai-system/safety-net.md`；本 pack 只是一種 Claude Code 實作方式。

## 包含內容

```text
implementation-packs/claude-safety-net/
  hooks/allow_trusted_script_permission.py
  hooks/allow_worktree_edit_permission.py
  templates/settings.snippet.json
  templates/settings.devops-readonly.example.json
  scripts/install-safety-net.sh
  scripts/probe-hook.py
```

## 不包含內容

不得打包：

- `.claude/settings.local.json`、auth、session、log、cache、shell snapshots
- 任何 token、password、cookie、bearer 或 credential 值
- 目標 workspace 的實際 host、namespace、客戶名或產品名

## 分層

| 層級 | 責任 |
|---|---|
| portable core | 語意 gate、制度、知識分層、approved-scripts 契約、`safety-net.md` 命令分類 |
| this pack | 把 approved-scripts/allow 與 `.worktrees/` 規則轉成 Claude Code runtime 的自動 permission |
| instance adapter | 特定 workspace 的 helper、環境、工具與 secret store |

## 導入方式

建議先 dry-run：

```sh
implementation-packs/claude-safety-net/scripts/install-safety-net.sh \
  --workspace <WORKSPACE_ROOT> \
  --dry-run
```

確認輸出後再加 `--apply`：

```sh
implementation-packs/claude-safety-net/scripts/install-safety-net.sh \
  --workspace <WORKSPACE_ROOT> \
  --apply
```

安裝腳本會：

- 安裝兩個 hook 到 `<WORKSPACE_ROOT>/.claude/hooks/`
- 產生已替換實際 workspace 路徑的 resolved settings snippet：`<WORKSPACE_ROOT>/.claude/portable-claude-safety-net.settings.snippet.json`
- 在 `settings.json` 不存在、為空，或已引用本 safety net 時，直接以 resolved snippet 建立 `settings.json`

它不會修改 `settings.local.json`、auth、sessions、logs 或 cache。

`--apply` 預設不覆寫既有 hook。若 `settings.json` 已存在且有未知內容，預設停止；確認要更新時先 dry-run，再使用：

```sh
implementation-packs/claude-safety-net/scripts/install-safety-net.sh \
  --workspace <WORKSPACE_ROOT> \
  --apply \
  --backup-existing
```

備份會放在：

```text
<WORKSPACE_ROOT>/.claude/backups/safety-net/<timestamp>-<pid>/
```

rollback 時，從該 backup directory 將 `hooks/` 與 `settings.json` 複製回對應位置。

若要人工合併既有 `settings.json`，優先合併 resolved snippet，因為其中已帶入實際 workspace 路徑。不要在未備份時直接覆蓋既有 settings。

## 驗證

```sh
python3 implementation-packs/claude-safety-net/scripts/probe-hook.py
```

probe 用獨立 temp workspace 跑服務中性案例（trusted script、唯讀 git、detached deny、`.worktrees/` 編輯、回退 ask 等）；全綠回傳 0。改 hook 後跑這支確認沒改壞。

## Hook 行為

`allow_trusted_script_permission.py`（PreToolUse / Bash）實作 `safety-net.md` 的 Bash 切片，做兩種機械式決策，其餘命令不輸出 decision、回到 Claude 正常 ask：

- **deny**：未受控 detached / 常駐服務（`&` 背景化、`nohup`、`disown`、`setsid`、`docker compose up -d`、`pm2 start`、`spring-boot:start`）。
- **allow**：執行 `ai-system/approved-scripts/allow/` 下的 trusted script、唯讀 git、`.worktrees/` 內 `git add` / `commit`，以及（在 sandbox 圍堵下）不會跑到沙箱外的本機命令。含 kubectl / gh / docker / helm / argocd / 網路 git / trusted-script 的命令走嚴格逐段驗證。

`allow_worktree_edit_permission.py`（PreToolUse / Edit·Write·MultiEdit·NotebookEdit）只 allow 目標路徑解析後落在 `<WORKSPACE_ROOT>/.worktrees/` 內的編輯（dot 路徑也吃得到，symlink / `..` 逃逸會解析到外部而退回 ask）。

兩個 hook 都靠環境變數參數化（`TRUSTED_SCRIPT_DIR`、`EXPECTED_CWD`），不含硬編碼 workspace 路徑。

## Settings 範本

- `templates/settings.snippet.json`：服務中性預設。含兩個 hook、唯讀 git 與 gh（GitHub CLI）allow、secret deny、`.worktrees/` 與 `/tmp` 編輯、sandbox 圍堵骨架；`denyWrite` 只保護套件自身（`ai-system`、`CLAUDE.md`、`AGENTS.md`、`.claude/hooks`）。`<WORKSPACE_ROOT>` 由安裝器替換。
- `templates/settings.devops-readonly.example.json`：kubectl / helm / argocd / docker 等 devops read-only allow 與 excludedCommands 範例。只有目標 workspace 確實使用這些工具時才合併進 `settings.json`。
