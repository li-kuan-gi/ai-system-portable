# Safety Net Contract

安全網是 portable system 的執行面。它負責把可機械化的邊界變成 sandbox、permission、hook、approved script、command policy 或其他 guardrail。

本檔只定義契約，不綁定任何單一 AI 服務或 launcher。

## 責任

安全網負責：

- 降低 agent 越界、誤執行或繞過受控 helper 的機率。
- 讓常見安全邊界由工具承擔，而不是只靠文字規則。
- 清楚標示哪些操作可自動允許、哪些需要 prompt、哪些禁止。
- 提供可驗證、可回復、可審查的導入方式。

安全網不負責：

- 判斷任務語意是否正確。
- 保存 auth、session、cache、log 或 secret。
- 取代 `rules.md` 的高回頭成本 gate。
- 讓 agent 或使用者臨場任意改寫已導入的保護結果。

## 正式來源

portable core 內的安全網來源分三層：

| 層級 | 來源 | 用途 |
|---|---|---|
| 契約 | `ai-system/safety-net/README.md` | 定義安全網應承擔什麼 |
| helper 分類 | `ai-system/approved-scripts/README.md` 與 `allow/`、`prompt/` | 定義 agent-facing executable 的授權分類 |
| 實作範例 | `implementation-packs/` | 示範特定 runtime 如何落地 |

execution layer 可以消費 `approved-scripts/allow`，但不應反過來把某個 runtime 的 permission table 當成制度本體。

## 實作結果變更規則

安全網導入到某個 instance 後，修改其實作結果應至少滿足：

1. 有明確目的：要降低哪個風險或成本。
2. 有明確範圍：會影響哪些 workspace、服務、helper 或 command prefix。
3. 有回復方式：能還原或手動修正。
4. 有驗證方式：dry-run、syntax check、config check 或實際低風險 probe。
5. 不修改私有狀態：auth、session、cache、log、secret 不得打包或覆蓋。
6. 有紀錄：寫入 portable patchlog 或目標 adapter 的正式變更紀錄。

若只是為了讓當前任務更方便而想繞過安全網，應停下回報，不直接改設定。

## 安全網知識

導入真實 workspace 時，adapter 或 implementation pack 應記錄：

- 使用了哪些 hook、permission、sandbox 或 command policy。
- 哪些 helper 會被自動允許，哪些需要 prompt。
- 安裝位置與人工合併步驟。
- 驗證方式與失效時的症狀。
- 回復方式。

這些是安全網知識；不應混入日常 `rules.md`，也不得包含 credential 值。
