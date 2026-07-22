---
name: debug
description: 調查 bug、error、exception、異常、不可重現問題、runtime/log 證據與 root cause；調查階段不修改 code、資料或遠端狀態。
---

# Debug

1. 先讀 `ai-system/skills/debug/references/workflow.md`。
2. 需要特定 runtime 或基礎設施證據時，使用 workspace 已登記的唯讀能力；沒有對應能力時列為 evidence gap。
3. 已取得 log 並需要分類錯誤或 source correlation 時，切換到 log-analysis。
4. 結論需要保留 code change 時，完成交接摘要後切換到 development。

輸出必須區分已確認事實、推測、證據缺口、根因、影響範圍與下一步選項。
