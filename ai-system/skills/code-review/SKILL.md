---
name: code-review
description: 審查程式碼或測試 diff、PR、review comment、regression 與測試缺口；以行為契約、資料流與下游消費者對帳為核心，只讀分析，不直接修改 code。
---

# Code Review

保持 read-only。若使用者要修正 finding，先完成審查結論，再回 `ai-system/skills/README.md` 路由到 development。

## 流程

1. 讀完需求、計畫、issue、review comment 或驗收條件。
2. 讀完整 diff，包含 production code、tests，以及明確屬於本次變更的 fixture/config。
3. 建立契約對帳：
   - 目標行為
   - 新增、修改或移除的可觀察狀態
   - 資料與控制流程的來源、轉換與 branch
   - API、DB、DTO、cache、UI、job、event、export 等下游消費者
   - 測試是否驗證輸入、輸出、持久化與 regression 契約
4. 不把「測試綠」或「計畫有寫」當成契約已完成。
5. 缺少必要 issue、runtime 或測試證據時，列為 evidence gap；缺口足以影響核心判斷時不得 pass。

## Fail 條件

- 行為與需求、計畫或驗收條件不一致。
- 新值只停在 local variable、request object、mock return 或 log，未到達應有 sink。
- 改名、預設值、單位、時機、錯誤處理或權限後，下游 consumer 未同步。
- 測試被弱化、只驗 mock 呼叫或只覆蓋 happy path，無法守住核心契約。

## 輸出

```markdown
verdict: pass|fail
findings:
- [severity] /absolute/path:line 具體問題、影響與建議修法
non_blocking:
- residual risk 或尚未取得的證據
```
