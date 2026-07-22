---
name: ui-verification
description: 在使用者指定的環境驗證 UI 行為、操作 Playwright、建立可回復測資並產出截圖；不得擅自替換環境或執行未授權遠端寫入。
---

# UI Verification

## 流程

1. 確認指定環境、URL、驗收條件、帳號狀態與是否需要建立資料。
2. 不以本機或其他 stage 取代指定目標；若公開 UI/API 足以驗證，不為了截圖額外查 cluster。
3. POST/PUT/PATCH/DELETE API 或建立測資屬遠端寫入，先說明影響與清理方式並取得確認。
4. 需要本機 UI 時，明確指定 backend URL，使用可由 managed session 停止的前景服務。
5. 使用 Playwright 時避免啟動不相關 web server；臨時 specs、test-results 與中間圖檔完成後清理。
6. 截圖前確認頁面完成載入、字型可用、icon font 未被一般中文字型覆蓋。
7. 回報驗證步驟、observed result、證據路徑、未驗證缺口與測資清理狀態。
