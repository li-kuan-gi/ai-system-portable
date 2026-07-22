# Workspace Skills

本檔是 workspace skill 的索引與任務路由入口。任務命中下列 skill 時，先讀對應 `SKILL.md`，再依 skill 指示讀 references / knowledge。

不要在入口階段預先掃整個 `ai-system/skills/` 或 `ai-system/knowledge/` 目錄。

skill 承載流程導覽與知識入口，不放 executable script。所有 agent-facing executable 一律使用 `ai-system/approved-scripts/`。

## Skill Index

### development

- 入口：`ai-system/skills/development/SKILL.md`
- 適用：程式碼開發、功能實作、功能修改、缺陷修正、補測試、重構、worktree 隔離、commit 前規劃，或 debug 後的修復實作。
- 主要任務語彙：implement、develop、feature、fix、refactor、test、實作、開發、修改、修 bug、補測試、重構。

### debug

- 入口：`ai-system/skills/debug/SKILL.md`
- 適用：調查 bug、error、exception、不可重現問題、runtime / log 證據與 root cause；調查階段不修改 code 或遠端狀態。
- 主要任務語彙：debug、root cause、exception、錯誤、異常、不可重現、調查。

### code-review

- 入口：`ai-system/skills/code-review/SKILL.md`
- 適用：審查完整 diff、PR、review comment、regression 與測試缺口。
- 主要任務語彙：review、code review、PR review、finding、regression、測試缺口、審查。

### technical-doc

- 入口：`ai-system/skills/technical-doc/SKILL.md`
- 適用：撰寫或大幅修改技術文件、規格、會議說明、資料模型與方案比較。
- 主要任務語彙：technical document、spec、design doc、meeting note、技術文件、規格、方案比較。

### log-analysis

- 入口：`ai-system/skills/log-analysis/SKILL.md`
- 適用：分析已取得的 log、stack trace、error / exception，分類錯誤並建立 root-cause hypothesis。
- 主要任務語彙：log、stack trace、exception、trace id、error pattern、日誌分析。

### chat-history

- 入口：`ai-system/skills/chat-history/SKILL.md`
- 適用：使用者明確要求查找或還原目前 workspace 的 Claude Code／Codex 對話，或稽核 agent 工具結果。
- 主要任務語彙：chat history、conversation、session、resume、對話歷史、找對話、還原對話、agent 行為稽核。

### ui-verification

- 入口：`ai-system/skills/ui-verification/SKILL.md`
- 適用：在指定環境驗證 UI 行為、操作 Playwright、建立可回復測資與產出截圖。
- 主要任務語彙：UI verification、Playwright、browser、screenshot、畫面驗證、截圖。

### system-audit

- 入口：`ai-system/skills/system-audit/SKILL.md`
- 適用：制度審計、規則衝突、制度制定、路由重排、分層整理、制度摩擦、agent 不遵守、安全網契約或安全邊界分類調整。
- 主要任務語彙：governance、audit、rules、conflict、routing、restructure、policy、safety net、hook、permission、sandbox、approved-scripts、制度、審計、規則、安全網。

### safety-net-sync

- 入口：`ai-system/skills/safety-net-sync/SKILL.md`
- 適用：把 safety-net contract 落實到已導入的 AI 服務、hooks、permissions、sandbox、rules 與 approved scripts，並驗證一致性。
- 主要任務語彙：safety-net sync、implementation pack、hook、permission、sandbox、config、execution layer、安全網實作。

### knowledge-maintenance

- 入口：`ai-system/skills/knowledge-maintenance/SKILL.md`
- 適用：整理知識、維護 skill index、修剪 references、檢查 repo 知識覆蓋度、維護環境 / context catalog、吸收 friction notes，或整理制度知識與安全網知識。
- 主要任務語彙：knowledge maintenance、skill cleanup、reference cleanup、coverage、friction notes、system knowledge、safety-net knowledge、知識治理、整理知識、制度知識、安全網知識。

## 任務切換

Skill 執行途中若遇到需要切換任務類型的情況，由當前 skill 說明切換時機與原因，agent 依本索引重新路由，繼續在同一對話中執行新任務。不需結束對話或開新 session。

Skill 文件中「發起 X 任務」即代表此類切換。切換步驟：

1. 在當前 skill 完成必要的交接摘要（例如 debug 結論、已確認事實、未決問題）。
2. 回到本索引，依任務描述重新路由到對應 skill。
3. 讀取新 skill 的 `SKILL.md` 繼續執行。

## Extension Point 模式

Portable skill 的 workflow 可能包含 **粗體概念詞**，代表「此處的做法依 workspace 能力決定」。這些稱為 extension point。

Extension point 的運作方式：

- Portable workflow 描述「做什麼」，用粗體概念詞標記「由 workspace 決定怎麼做」的位置。
- Workspace 的 `skills/README.md` 登記對應 skill，觸發字對齊該概念詞。
- Agent 執行到 extension point 時，查 README 是否有對應 skill；有則交由該 skill 處理，無則自行判斷或詢問使用者。

**範例**：portable `development` workflow 寫「執行**技術探索**（依 workspace 能力）」。Workspace 若有觸發字包含「技術探索」的 skill，agent 就路由過去；沒有則自行探索。

Workspace skill 的 extension point 覆蓋範圍由觸發字決定，portable skill 不需要知道 workspace skill 的存在。

## 新增 Workspace Skill 的判準

只有同時符合以下條件時才新增 skill：

1. 任務反覆出現，值得路由化。
2. 流程穩定到可以文件化。
3. skill 能降低後續查找、澄清或誤判成本。
4. skill 入口可以保持短小，細節放 references，而不是把 `SKILL.md` 寫成大型手冊。

instance-specific skill 可以登記在本 index，但若要重新發布 portable core，應清楚區分哪些是 portable、哪些是 adapter。
