# Debug 調查流程

## 1. 邊界

- 只調查，不建立 commit、不修資料、不改遠端狀態。
- 可做本機重現與一次性驗證；若結果要保留，轉 development。
- 每個假設都要用證據支持或排除。
- 網路、權限、runtime、log、API、DB 或 helper 不可用時，列 evidence gap，不用舊資料補成現況。

## 2. 收案

確認：

- observed failure、時間點、是否可重現
- 問題來源與必要附件
- 本機或遠端環境
- 服務、版本、repo/ref 與 runtime revision
- trace/request/case identifier

若環境或版本不明且會影響根因判斷，先停下。

## 3. 排查

每輪只驗一個主要假設，記錄：

```text
假設 -> 查了什麼 -> 看到什麼 -> 支持／排除什麼 -> 下一步
```

- log：限縮時間窗、服務、identifier 與輸出量；不要回貼大量 raw log。
- API/DB：只讀。
- code：優先使用明確 ref；需要完整 filesystem 時使用 detached worktree。
- runtime / infrastructure：使用 workspace 已登記的唯讀能力；portable core 不假設特定平台。

多個假設都不成立時，重新確認環境、版本、資料、時間窗與問題描述，不要直接跳到修法。

## 4. 報告

至少包含：

- 問題與調查範圍
- 每輪假設與證據
- 根因或已排除方向
- 一手事實、推測與不可得證據
- 影響範圍
- 不修改、補證據、修 code、改資料/runtime 等下一步選項
