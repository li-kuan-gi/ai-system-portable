# 知識治理

## 觸發

使用者要求整理知識、檢查覆蓋度、修剪 skill / reference、維護 skill index、更新環境 / context catalog，或吸收 friction notes 時使用本 skill。

## 任務

確保知識資產正確、精簡、可用。這不是美化文件，而是替下一個 agent 做品質控管。

思考時站在執行任務的 agent 視角：下一個 agent 能不能快速找到正確入口、正確理解並真的遵守？

責任模型看 `ai-system/governance/contracts.md`，共通原則看 `ai-system/governance/principles.md`；修改邊界看 `ai-system/rules.md` 與 `ai-system/constraints-detail.md`。

## 紀錄寫入

新增中央修訂紀錄時，使用：

```text
ai-system/approved-scripts/allow/patchlog-append
```

新增制度摩擦紀錄時，使用：

```text
ai-system/approved-scripts/allow/friction-notes-append
```

若 append helper 因 sandbox、read-only filesystem 或 permission 類錯誤失敗，先用同一公開入口走受控執行路徑重跑。只有 helper 不存在、重跑後仍失敗或格式不支援時，才手動追加。

## 巡檢步驟

### 1. 標註可見範圍

- **中央制度模式**：僅巡檢 `ai-system/` 中央文件
- **部分拓撲模式**：中央文件 + 目前 workspace 可見 repo
- **完整拓撲模式**：所有預期 repo 都在場

若預期 repo 未掛載，相關檢查項標註為「證據不可得」。

### 2. Skill 與 Reference 品質

檢查：

- `ai-system/skills/*/SKILL.md`
- `ai-system/skills/*/references/`
- workspace knowledge files
- workspace skill references / workflow 入口

workspace task skill 只登記在 `ai-system/skills/`。若日常任務入口指向外部或 hidden skill-like 目錄，應改由 workspace skill、skill reference 或 approved wrapper 承接。

評估：

- 正確性：步驟是否對應目前 helper 與 workspace knowledge
- 重複性：是否有高度重疊的 skill reference / workflow
- 新鮮度：是否有過時 workflow 或 reference
- 可及性：正式入口是否存在且指向真實檔案
- 分層：任務細節是否被錯放進日常入口規則

### 3. 分類待沉澱內容

正式沉澱前，先判斷：

- **認知層**：事實、現況、命名、查法、判準
- **實踐層**：做法、步驟、workaround、script、流程骨架、template

同時判斷內容屬於制度知識、安全網知識、知識系統知識或任務知識。不要把安全網實作細節塞回日常 rules，也不要讓任務知識變成制度判準。

所有新事實或流程都需要來源與查證程度。未查證內容不得寫成已驗證事實。

### 4. 覆蓋度檢查

檢查：

- `rules.md` 是否只指向 workspace skill index
- skill index 是否都指向存在的 `SKILL.md`
- 任務專項分流是否落在對應 skill
- workspace-specific facts 是否落在 `ai-system/knowledge/` 或 adapter 定義的位置
- 安全網知識是否能說明目前哪些保護是機械執行、如何驗證、如何回復
- 知識系統知識是否能說明知識如何保存、查詢、索引、更新與淘汰
- 任務知識是否能支援實際任務查證，而不把流程或制度判準混入事實文件
- 重複工作流是否已有 skill reference 或 workspace skill
- 已存在但未被入口使用的 skill / reference 是否應補登或淘汰

### 5. Friction notes 轉知識

讀 `ai-system/governance/friction_notes.md`，找出：

- 已解決但應沉澱為 skill reference、knowledge、tool note 或 template 的摩擦
- 反覆出現且需要新 workflow 或 helper 的摩擦
- 已過時、可在治理整理時摘要或刪除的摩擦

未解決制度摩擦的預設暫存落點是 `governance/friction_notes.md`。只有模式穩定且值得承擔認知成本時，才升級到 rules、constraints、skill references 或 tools。

### 6. Approved helper 文件

知識若貼近 helper，依層級放置：

- command usage 與參數 -> wrapper `--help`
- helper family 分類與共同 caveat -> `ai-system/approved-scripts/README.md`
- 跨任務事實 -> `ai-system/knowledge/context/` 或 skill reference

不要在 `approved-scripts/` 之外建立旁路 script 目錄。

## 產出格式

```markdown
## 知識治理報告
- 日期：
- 觸發原因：
- 可見範圍：

## Skill 狀態
| 知識資產 | 狀態 | 建議動作 |
|---|---|---|
| ai-system/skills/<skill>/SKILL.md | 正常 / 需更新 / 過時 | |

## 覆蓋度缺口
- 尚未定義 instance knowledge 介面但任務需要 workspace-specific facts：
- 缺 skill / SOP 的重複任務：
- 正式入口 vs 實際檔案不一致：

## 待轉化的 friction notes
| friction note | 應沉澱到 | 摘要 |
|---|---|---|

## 建議下一步
1. ...
```
