# 制度審計與重整

## 觸發

使用者提到制度檢視、規則衝突、agent 不遵守、制度制定、路由整理、分層重排或制度摩擦時使用本 skill。

## 任務

你不是在維護文件格式。你是在診斷一個系統：使用者是 agent，產品是制度文件。

你的工作是找出 agent 為什麼會誤讀、漏讀或不遵守的結構性原因。思考時站在執行任務的 agent 視角：它會先看到什麼、如何誤解、為什麼停錯或做錯。

修改制度前，必須先判斷每段文字的主要讀者與任務情境。不要把只給制度維護者看的整理規則放進日常任務 agent 的入口心智模型。

責任模型看 `ai-system/governance/contracts.md`，共通原則看 `ai-system/governance/principles.md`；修改邊界看 `ai-system/rules.md` 與 `ai-system/constraints-detail.md`。本 skill 只負責審計與制度重整流程。

## 紀錄寫入

新增中央制度修訂紀錄時，使用：

```text
ai-system/approved-scripts/allow/patchlog-append
```

新增制度摩擦紀錄時，使用：

```text
ai-system/approved-scripts/allow/friction-notes-append
```

若 append helper 因 sandbox、read-only filesystem 或 permission 類錯誤失敗，先用同一公開入口走受控執行路徑重跑。只有 helper 不存在、重跑後仍失敗或格式不支援時，才手動追加。

## 審計步驟

### 1. 標註可見範圍

- **中央制度模式**：僅審查 `ai-system/` 中央文件與可見證據
- **部分拓撲模式**：中央文件 + 目前 workspace 可見 repo
- **完整拓撲模式**：所有預期制度文件與 repo 都在場

若預期 repo 未掛載，相關檢查項標註為「證據不可得」。

先看行為證據，再用制度文件解釋：

- 任務對話或使用者描述的失敗案例
- `ai-system/governance/friction_notes.md`
- `ai-system/governance/patchlog.md`
- 使用者提供的具體案例

再讀制度文件：

- `rules.md`
- `governance/contracts.md`
- `constraints-detail.md`
- 命中的 skills
- `governance/principles.md`

### 2. 檢查限制有效性

檢查：

- `rules.md` 的限制是否精準
- 是否有寫了但 agent 持續違反的限制
- 可機械攔截的反覆失敗是否應升級為 hook / tool
- 文字規則與安全網契約是否分工清楚
- 限制之間是否衝突
- 措辭是否會讓不同 agent 做出不同判斷

### 3. 檢查知識可及性

檢查：

- agent 是否讀到該讀的文件
- skill 步驟是否對應目前 scripts 與 workspace knowledge
- 日常任務入口是否只指向 `ai-system/skills/` 下的 workspace skill
- 是否有該沉澱但尚未寫下的經驗

### 4. 檢查認知負荷

對每段要新增、搬移或改寫的文字，標示：

- 主要讀者：日常任務 agent、特定 skill agent、制度 / 知識維護 agent、工具 / 安全邊界維護者
- 讀取時機：日常入口、任務路由、制度審計、知識治理、工具實作
- 正確層級：principles、rules、constraints、skill、reference、knowledge、tool docs、record

`rules.md` 應只保留最小硬限制、任務流程入口、高回頭成本 gate 與少量補充原則。

### 5. 跨層一致性檢查

提出可執行修改前，回答：

- 這次修改應落在哪一層
- 主要讀者是誰
- 日常 agent 沒讀到新增文字時，是否仍能正確完成一般任務
- 是否影響 principles、`rules.md`、constraints、skill steps、records 或 tool docs
- 若不同步修改，後續 agent 可能在哪裡誤解或做出相反判斷

若範圍不明或跨層衝突存在，先回報衝突與建議處理範圍，不直接落檔。

## 產出格式

```markdown
## 審計摘要
- 日期：
- 觸發原因：
- 可見範圍：

## 發現

### 發現 1：<標題>
- 現象：
- 證據狀態：已查證 / 部分查證 / 條文推論
- 問題層級：條文 / 分層 / 上位原則
- 主要受影響讀者：
- 根因：
- 短期修補：
- 骨架調整：
- 預期效果：

## 限制有效性
| 限制 | 狀態 | 備註 |
|---|---|---|
| 硬限制 | 有效 / 偶有違反 / 頻繁違反 | |
| 停下 gate | 有效 / 偶有違反 / 頻繁違反 | |
| 補充原則 | 有效 / 偶有違反 / 頻繁違反 | |
| 治理原則 | 有效 / 偶有違反 / 頻繁違反 | |

## 建議下一步
1. ...
```
