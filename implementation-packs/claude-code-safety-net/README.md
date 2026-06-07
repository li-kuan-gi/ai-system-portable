# Claude Code Safety-Net Implementation Pack

本 pack 是 portable core 的 **Claude Code execution layer 實作**。

portable core 定義安全網與 approved-scripts 契約；本 pack 示範如何在 `.claude/` 內落地。
正式安全網契約見 `ai-system/safety-net/README.md`。

## 包含內容

```
implementation-packs/claude-code-safety-net/
  hooks/allow_trusted_script_permission.py   # Bash PreToolUse hook
  hooks/allow_worktree_edit_permission.py    # Edit/Write PreToolUse hook
  settings.snippet.json                      # Claude Code settings 範本
```

## Hook 行為

`allow_trusted_script_permission.py`：

- **deny**：未受控 detached 服務（`&`、`nohup`、`pm2 start`、`docker compose up -d` 等）
- **allow**：trusted script（`approved-scripts/allow/`）、唯讀 git、路徑限 workspace/tmp 的讀取命令
- **no_decision**：explore 類（python3 -c、find 等）及其他命令交回 Claude Code 判斷

explore 不依賴 anchor 且沙箱可能被 dangerouslyDisableSandbox 繞過，一律 no_decision；
沙箱開啟時由 `autoAllowBashIfSandboxed` 接手。

`allow_worktree_edit_permission.py`：

- **allow**：Edit/Write/MultiEdit/NotebookEdit 目標落在 `.worktrees/` 內
- **no_decision**：其他目標

## 導入方式

```sh
cp implementation-packs/claude-code-safety-net/hooks/*.py .claude/hooks/
# 合併 settings.snippet.json，將 <WORKSPACE_ROOT> / <CLAUDE_HOME> 換成實際路徑
```

## 更新 Instance

Portable pack hook 更新後：

```sh
cp implementation-packs/claude-code-safety-net/hooks/allow_trusted_script_permission.py .claude/hooks/
cp implementation-packs/claude-code-safety-net/hooks/allow_worktree_edit_permission.py .claude/hooks/
```

## 分層

| 層級 | 責任 |
|---|---|
| portable core | 語意 gate、制度、安全網契約、approved-scripts 分類 |
| this pack | approved-scripts/allow → Claude Code 自動 approval |
| instance adapter | workspace 特定 helper、環境、工具 |
