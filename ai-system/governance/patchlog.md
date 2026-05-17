# Cross-Repo Patch Log

本檔記錄 portable package 導入到實際 workspace 後，該 workspace 的制度核心、入口 adapter、service pack、implementation pack 與模板修訂軌跡，供後續 agent 與維護者抽查制度演化。

本檔在 portable package 中應保持初始化狀態。導入到實際 workspace 後，才由該 workspace 的 agent 追加紀錄。

本檔只保留：

1. 現行中央文件的修訂規則
2. 仍對現行制度有說明價值的修訂紀錄

已無現行操作價值的舊歷史，應在治理整理時封存或摘要。

## 寫入規則

- 每次修訂追加一條紀錄。
- 本檔只記 portable package 內的制度核心、入口 adapter、service pack、implementation pack、模板與 package-level docs 變更。
- instance adapter 的知識紀錄若需要另設位置，應由該 adapter 自行指定寫入規則。
- 直改補缺與正規提案都可記錄，但必須說明證據與影響範圍。
- 新增紀錄時優先使用 `ai-system/approved-scripts/allow/patchlog-append`。
- 若 helper 因 sandbox、read-only filesystem 或 permission 類錯誤失敗，先用同一公開入口走受控執行路徑重跑。
- 只有 helper 不存在、重跑後仍失敗或格式不支援時，才手動追加。
- 不得寫入 secret、token、password 或 credential 值。

## 每條必備欄位

```markdown
## YYYY-MM-DD · <任務 / 角色> · <被修訂檔案路徑>

**修訂類型**：補缺 / 補欄位 / 正規提案
**變更摘要**：一句話說明
**來源證據**：
- <code path / runtime / API / 本機檢查 / 使用者要求>
**任務情境**：這次為什麼碰到這個缺口
```

## 直改條件

正式判準以 `ai-system/constraints-detail.md` 的「可證據化的事實補缺」為準；本檔只記錄修訂軌跡，不重列完整 gate。

---

## 修訂紀錄

目前沒有修訂紀錄。
