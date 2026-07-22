---
name: chat-history
description: 在使用者明確要求時，查找或還原目前 workspace 的本機 Claude Code／Codex 對話，並分析工具結果；不得用於掃描無關 workspace。
---

# Chat History

只有使用者明確要求查找歷史、還原對話或稽核 agent 行為時才使用。

公開入口：

```text
<WORKSPACE_ROOT>/ai-system/approved-scripts/allow/chat-history prompts [--since YYYY-MM-DD] [--source claude|codex|both]
<WORKSPACE_ROOT>/ai-system/approved-scripts/allow/chat-history grep <pattern> [--in prompt|output|both]
<WORKSPACE_ROOT>/ai-system/approved-scripts/allow/chat-history dump <session-id> [--tail N]
<WORKSPACE_ROOT>/ai-system/approved-scripts/allow/chat-history tools <session-id> [--fails-only]
<WORKSPACE_ROOT>/ai-system/approved-scripts/allow/chat-history fails [--since YYYY-MM-DD]
```

邊界：

- 只接受 session metadata 的工作目錄位於目前 workspace 的紀錄。
- session id 必須是至少 8 字元的十六進位 UUID prefix，且只能命中一筆。
- 輸出會限制長度並做敏感值遮蔽；仍應把對話歷史視為私有資料，不貼入 issue、PR 或 git-tracked 檔案。
- 不讀取 auth 或 credential store，不修改、搬移或打包 service-managed session files。

Outcome 必須分開：

- `fail`：執行真的失敗。
- `denied`：使用者拒絕工具呼叫。
- `blocked`：hook、policy 或 safety net 阻擋。

不得用 reasoning 文字、command echo 或被讀入的檔案內容判定工具失敗；只使用配對後的 tool result 訊號。
