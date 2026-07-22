---
name: log-analysis
description: 分析已取得的 log、stack trace、error/exception 訊息，分類錯誤、建立 root-cause hypothesis 並比對 source code；不負責取得遠端 log。
---

# Log Analysis

保持 read-only，不修改 code 或遠端狀態。

## 流程

1. 確認來源、時間窗、服務/container、trace/request id 與 observed failure。
2. 分類 application、HTTP、timeout/network/TLS、DB、auth、resource/OOM/restart 等錯誤。
3. 抽出最小有效證據：第一個 error、最接近 root cause 的 `Caused by`、identifier、版本/profile 線索。
4. source correlation 優先使用明確 git ref；需要完整 view 時使用 detached worktree。
5. 輸出一手事實、推測、證據缺口與下一步。

大量 raw log 先保存至 `/tmp`，只回報必要摘錄、摘要與路徑；輸出前遮蔽 credential。
