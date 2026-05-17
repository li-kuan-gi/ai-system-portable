# Agent Friction Notes

本檔記錄執行任務時出現的制度摩擦，目的不是抱怨，而是幫助後續 agent 與維護者判斷：

1. 哪些摩擦還沒被制度吸收
2. 哪些問題已被現行文件處理，但值得保留短摘要

本檔在 portable package 中應保持初始化狀態。導入到實際 workspace 後，才由該 workspace 的 agent 追加紀錄。

## 寫入規則

- 只記錄仍會影響後續任務判斷的摩擦。
- 新增紀錄時優先使用 `ai-system/approved-scripts/allow/friction-notes-append`。
- helper 只會追加到「待處理追加紀錄」區段。
- 若 helper 因 sandbox、read-only filesystem 或 permission 類錯誤失敗，先用同一公開入口走受控執行路徑重跑。
- 只有 helper 不存在、重跑後仍失敗或格式不支援時，才手動追加。
- 新增紀錄必須包含來源證據。
- 不得寫入 secret、token、password 或其他 credential 值。
- 若問題已被現行制度吸收，改寫為短摘要，不保留長篇歷史敘事。
- 若內容已無現行制度價值，治理整理時可刪除。

## 新增紀錄必備欄位

```markdown
### <摩擦標題>

- **首次發現**：YYYY-MM-DD
- **現象**：具體失敗或混亂
- **來源證據**：
  - <使用者描述 / 本機檢查 / 文件 / code path / runtime / API / log 證據>
- **為何屬制度摩擦**：為什麼這是路由、規則、工具或知識分層造成，而不是單次執行錯誤
- **對後續 agent 的判斷提醒**：
  - <下次遇到相同訊號時應如何判斷>
- **建議吸收方向**：
  - <目標層級：rule、constraint、skill、knowledge、tool、template 或 record>
```

---

## 待處理

目前沒有待處理摩擦。

---

## 已吸收摘要

目前沒有已吸收摘要。

---

## 待處理追加紀錄

新增摩擦請用 `ai-system/approved-scripts/allow/friction-notes-append` 追加在本節。
