# Knowledge

本目錄存放已驗證且可重用的知識。知識是 portable system 的事實面，不只保存任務事實，也保存制度、安全網與知識系統本身的可查證脈絡；正式責任模型見 `ai-system/governance/contracts.md`。

分工：

- `context/`：跨 repo 或 workspace-level 事實、拓撲、環境 catalog、查詢路徑、共享邊界、agent-readable 歷史摘要與設定
- `domains/`：目前 workspace 的穩定 domain 概念、業務詞彙或產品語彙

知識系統應能處理：

- **制度知識**：制度的正式來源、設計原因、歷史修訂與仍有效的治理脈絡。例如「制度分為制度、知識、安全網」。
- **安全網知識**：目前哪些邊界由角色權限、sandbox、hook、approved scripts 或 implementation pack 機械執行，以及如何驗證與回復。
- **知識系統知識**：知識如何被保存、查詢、索引、更新與淘汰。例如 RAG 實作、索引範圍、來源標示與查證程度。
- **任務知識**：特定任務、domain、repo、API、環境、流程、業務語彙、常見錯誤與查證路徑。

正式制度判準仍在 `rules.md`、`constraints-detail.md` 與 `governance/principles.md`；知識文件不應形成第二套規則。

規則：

- 正式沉澱前先標註來源與查證程度。
- 不得寫入 secret、token、password 或 credential 值。
- 歷史對話與設定應以可查證、可安全閱讀的摘要保存；不要把 raw service session、auth state 或 cache 當成 portable core 內容。
- 快速變動的 instance state 不應混進治理原則。
- workspace-specific facts 應依目前 workspace adapter 定義的正式位置沉澱；portable core 不預設 repo 內知識介面。
