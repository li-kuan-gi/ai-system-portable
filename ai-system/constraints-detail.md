# 行為限制細則

本檔供制度審計、安全邊界實作，或日常任務在高回頭成本 / 邊界模糊時按需使用；不是日常任務 agent 的 L0 心智模型。

安全邊界一律看操作的實際影響面與風險，不綁定特定 launcher、wrapper、sandbox、proxy 或其他實作名詞。

## 快速索引

日常任務不要通讀本檔；只查對應小節：

- 不確定能不能做 -> `判斷順序`、`風險分類`
- approved helper 或命令組合 -> `Approved script 優先`
- hook、permission、sandbox、approved-scripts 分類或 rules profile 變更 -> `安全網變更`
- git fetch / pull、repo filesystem、ref 查詢或 worktree -> `Git 同步與 worktree 隔離`
- 本機 dev server、watcher 或長時間服務 -> `本機服務`
- 遠端 runtime、API、DB、log 或部署狀態 -> `遠端、資料與環境邊界`
- secret、token、password、robot account 或本機工具憑證 -> `Secret 與 token`
- 網路、API、DB、log、helper 或本機 runtime blocker -> `關鍵依賴失效`
- 文件補缺、patchlog 或 append helper -> `文件補缺與 patchlog`

## 0. 判斷順序

遇到不確定能不能做的操作時，依序判斷：

1. 先看實際影響面：是否缺少足夠事實、是否跨出本機、是否碰到共享邊界、是否不可逆，或是否屬高回頭成本。
2. 若是任務語意層的高回頭成本，回到 `rules.md` 的停下 gate 先整理方案。
3. 若是安全邊界實作或命令分類問題，再分類為 `allow` / `prompt` / `forbidden`。
4. 若 `ai-system/approved-scripts/allow/` 或 `prompt/` 已有單一功能入口，優先使用該入口。
5. 若要修改安全網實作或分類結果，先走 `安全網變更` gate。
6. 若會碰遠端 runtime、API、DB、log 或部署狀態，先確認完整目標，例如 `<env-key> / <stage>`。
7. 若關鍵依賴失效且影響定位、判斷、驗證或交付，立即回報 blocker，不得用猜測或舊資料補現況。

### 現況優先

永遠以當前可驗證的 runtime / API / DB / code / 系統事實為優先依據。本機腳本、文件、檔名、註解與舊案例都只能作為線索。

## 1. 風險分類

核心判準不是單純有沒有寫入，而是是否缺少足夠事實、會不會跨出本機、碰到共享邊界，或造成不可逆後果。

- **allow**：read-only 工作、本機可逆修改、草稿整理、測試與驗證、`git fetch`、受控 safe pull helper。
- **prompt**：事實不足、制度不明或制度矛盾、影響非本機服務、共享協作承諾、可控但不可逆或高回頭成本操作。
- **forbidden**：secret 外洩、繞過 policy、未受控 detached 長時間服務、無法界定目標 / 影響 / recovery 的破壞性操作。

具體命令的 allow / prompt / forbidden 分類以 `ai-system/safety-net.md` 為唯一正式來源，本檔不另列命令表。

## 2. 本機執行邊界

### Approved script 優先

若 `ai-system/approved-scripts/allow/` 或 `prompt/` 已有單一功能入口覆蓋當前需求，使用該公開入口，不要先自行重拼底層命令。

- `allow/` 入口是窄範圍 read-only / inspect / validate helper，或明確受控的本機輸出 / append / smoke test helper。
- `prompt/` 入口是需要確認或更高安全處理的受控執行入口。
- 不得直接執行 `approved-scripts/_lib/`。
- 只有入口不存在、入口無法覆蓋需求、入口失敗，或使用者明確要求不用 helper 時，才自訂命令或提出新增 helper。
- 既有 helper 失敗時，保留錯誤證據並回報缺口；若需求可重用或涉及 credential、遠端查詢、command policy，優先新增或調整單一功能 approved script。
- `allow/` 目錄是 approved helper 分類的 source of truth；execution layer 應消費這個目錄，不要維護第二份逐檔清單。

### 安全網變更

安全網包含 hook、permission、sandbox、command policy、approved-scripts 分類、rules profile、installer 與其他會影響 agent 可執行邊界的機械式保護。

修改安全網實作或分類結果預設屬 `prompt`。執行前必須交代：

- 目的：要降低哪個風險或成本
- 影響範圍：會影響哪些 workspace、AI 服務、helper 或 command prefix
- 變更內容：新增、移除或調整的檔案與分類
- 驗證方式：dry-run、syntax check、config check 或低風險 probe
- recovery：如何回復或人工修正
- 紀錄位置：portable patchlog 或目標 adapter 的正式紀錄

不得為了讓當前任務更方便而繞過安全網。若只是一次性需要例外，先停下回報需求與替代方案。

### Git 同步與 worktree 隔離

`git fetch` 與受控 safe pull helper 只同步本機 repo 狀態，不發布、不建立共享協作承諾。safe pull 是 `allow/` 的受控本機 repo 狀態變更例外，不代表所有 `allow/` helper 都可任意修改本機狀態。

- 自主 fast-forward pull 使用 `ai-system/approved-scripts/allow/git-pull-ff-only-clean <repo>`。
- 若 worktree 不乾淨、需要 merge commit / rebase、發生 conflict，或會覆蓋既有變更，立即停下回報。
- 不同 branch 的 read-only 查詢優先用 ref-based query：`git show <ref>:<path>`、`git diff <ref-a>..<ref-b>`、`git ls-tree <ref>`。
- repo filesystem 是共享邊界；不要假設共享 checkout 在其他 agent 或使用者操作時保持穩定。
- 需要完整 filesystem view 做 read-only 分析時，建立 detached task worktree。
- 任何會改變 repo filesystem 或本機執行狀態的工作，使用獨立 branch task worktree / workdir。
- worktree 路徑慣例：`.worktrees/<task>/<repo>/<slot>`。
- 使用：
  - `ai-system/approved-scripts/allow/git-worktree-add-detached <repo> <task> <slot> <ref>`
  - `ai-system/approved-scripts/allow/git-worktree-add-branch <repo> <task> <slot> <start-ref>`
  - `ai-system/approved-scripts/allow/git-worktree-remove-clean <worktree-dir>`

worktree 只隔離 repo filesystem 與 branch / HEAD 狀態，不隔離 port、database、container、cache、credential、remote API 或其他共享資源。

### 本機服務

agent 啟動本機 service、dev server、watcher 或長時間 worker 時，優先使用可由同一 terminal / managed session 停止的方式。

- **foreground / managed session**：優先使用。
- **managed detached**：只有透過 approved wrapper 才可使用；wrapper 必須記錄 stop handle 並驗證清理。
- **unmanaged detached**：禁止。

若服務無法正常停止，或任務確有 managed detached 必要，執行前先說明原因、啟動命令、停止命令與清理驗證方式。

## 3. 遠端、資料與環境邊界

### Read-only 查詢

read-only 查詢可自主執行，前提是不改變共享狀態、不持久化 secret，且目標身分明確。

例子：

- read-only API
- SQL SELECT
- dashboard / log / metric 查詢
- infra status 查詢

### 遠端或資料寫入

infra、共享 runtime、部署、資料層寫入與業務系統寫入通常屬高回頭成本。執行前必須交代：

- 目標環境 / namespace / app / resource
- 完整命令或操作
- 預期影響範圍
- 驗證方式
- rollback / recovery 方案
- 不確定性與缺口

若目標、影響或 recovery 無法界定，不得執行。

### 環境身分

遠端目標應用完整身分描述，例如 `<env-key> / <stage>`，不要只用模糊短名。

- namespace、host、profile、cluster 常是定位線索，不等於完整環境身分。
- 同一 env-key 的不同 stage 可能有不同 namespace、host、profile、資料來源與 log。
- 若 stage 不明且任務會碰 runtime、API、DB、log 或部署狀態，必須先釐清。
- 不得用某個 stage 的 runtime 現況推論另一個 stage。

### 資料與環境事實

本檔只保留通用邊界，不承載特定 repo 現況。資料異動通道、schema 細節、環境型別反例與已驗證 target catalog 應寫在 instance adapter 或 `ai-system/knowledge/context/`。

通用原則：

1. 資料異動通道以目前 runtime / API / DB 現況為準。
2. 環境型別與資料來源以目前 runtime 設定為準，不憑檔名或舊案例推論。

## 4. Secret 與 token

### Tier A：短效或個人憑證

例子：

- bearer token
- 個人 SSO / OIDC token
- 使用者密碼
- DB / cache 密碼

僅在當前 session 記憶體中使用，不寫入檔案。

### Tier B：長效 robot / service credential

只有同時符合以下條件，才可持久化：

1. 目標 repo 存在，且 agent 正在該 repo 範圍內工作。
2. 目的路徑已驗證不會進入 git-tracked diff。
3. repo 有 ignore 規則或慣例證明該路徑是 local-only。
4. 不寫入 `.md` 或 git-tracked 路徑。
5. script 支援 env var override。
6. 檔頭註記 account 名稱與用途，但不暴露 secret。

任一條件不成立，視為只能留在 session 使用。

### Tier C：本機工具憑證

長效本機工具憑證應放在 workspace 外，例如：

```text
<user-local-secret-store>/<service>/.env
```

條件：

1. directory permission 應為 `0700`，file permission 應為 `0600`
2. 不在 workspace、`.md` 或 git-tracked 路徑內
3. 文件只記路徑與變數名，不記實際值
4. helper 應支援 explicit env var override，再讀本機 secret store
5. 遷移時不得回顯 secret 值

識別有疑義時，一律當 Tier A 處理。

## 5. 證據、備份與回報

### 證據強度

- 一手事實：直接讀到的 code、runtime response、API result、DB result 或使用者明確需求
- 多點事實推論：標註為推測 / 假設
- 沒有證據：不要寫成事實，改成詢問或查證

影響決策的不確定性必須放在前段摘要。

### 備份

| 操作 | 備份 |
|---|---|
| API change | 先 GET 舊資料成 local JSON |
| SQL change | 先 SELECT 受影響列成 local file |
| file change | 保留在 git diff，或未版本化時建立 local backup |
| runtime / deploy change | 先走停下 gate，附驗證與 recovery 方案 |

### 發現即回報

調查時若發現現況與使用者描述不一致，立即回報並提出替代方案，不要靠猜測繼續。

## 6. 關鍵依賴失效

關鍵依賴包含網路、登入 / 權限、runtime 狀態、log、API / DB access、approved helper、本機 build / test / dev runtime，或任何影響定位、判斷、驗證、交付的依賴。

當關鍵依賴失效：

1. 判斷是否阻塞本次任務。
2. 做一次或少量低風險 precheck / retry。
3. 仍阻塞時，用 3-7 行回報：阻塞依賴、錯誤摘要、已嘗試路徑、受影響後續步驟、可選替代方案或需要使用者協助的事項。
4. 不得用舊文件、cached output 或推測補現況。
5. 只有剩餘工作明確不依賴該 blocker 時，才繼續做本機獨立工作，並標註剩餘驗證風險。

## 7. 文件補缺與 patchlog

### 可證據化的事實補缺

同時滿足以下條件時，可直接修改文件並追加 patchlog：

1. 補的是 code / runtime / API / DB 證據中已存在的事實。
2. 不刪除、不搬遷、不改變既有條文語意。
3. 不涉及跨層搬遷。
4. 範圍小。
5. patchlog 有明確來源證據。

否則先回報風險、草稿或方案。

Patchlog 位置：

- 中央制度變更 -> `ai-system/governance/patchlog.md`

### Append helpers

使用：

- `ai-system/approved-scripts/allow/patchlog-append`
- `ai-system/approved-scripts/allow/friction-notes-append`

這些 helper 是 append-only 的窄例外，不放寬一般文件編修、結構重整或高回頭成本制度修改 gate。
