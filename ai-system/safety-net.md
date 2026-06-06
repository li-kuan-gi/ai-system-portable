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
| 契約 | `ai-system/safety-net.md` | 定義安全網應承擔什麼、命令如何分類 |
| helper 分類 | `ai-system/approved-scripts/README.md` 與 `allow/`、`prompt/` | 定義 agent-facing executable 的授權分類 |
| 實作範例 | `implementation-packs/` | 示範特定 runtime 如何落地 |

execution layer 可以消費 `approved-scripts/allow`，但不應反過來把某個 runtime 的 permission table 當成制度本體。

## 命令分類

本檔是 portable core 命令 allow / prompt / forbidden 分類的唯一正式來源；其他制度文件不另列命令表。判準不是單純有沒有寫入，而是是否缺少足夠事實、會不會跨出本機、碰到共享邊界，或造成不可逆後果。

| 類型 | 預設 |
|---|---|
| GET API、SQL SELECT、讀檔、read-only log、`git log/diff/fetch` | allow |
| 本機可逆 code / 文件修改 | allow |
| `approved-scripts/allow/` 下入口、受控 safe pull helper（clean worktree、fast-forward） | allow |
| commit、push、PR、merge、release、deploy、對外發布 | prompt |
| POST/PUT/PATCH/DELETE API、SQL mutation、infra mutation、共享 runtime restart | prompt |
| hook、permission、sandbox、approved-scripts 分類、rules profile 或 safety-net installer 變更 | prompt |
| `approved-scripts/prompt/` 下入口 | prompt |
| 破壞性本機操作 | prompt；若影響與 recovery 無法界定則 forbidden |
| secret 寫入 `.md` 或 git-tracked 檔案 | forbidden |
| unmanaged detached service | forbidden |

預設值：未列入 allow 的命令，預設歸 prompt。各 AI 服務的 execution layer 可把 prompt 縮窄為更嚴，不得放寬。

具體命令的判斷情境與邊界細則見 `ai-system/constraints-detail.md`；本檔只定義分類結果。

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
