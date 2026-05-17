# Workspace Skills

本檔是 workspace skill 的索引與任務路由入口。任務命中下列 skill 時，先讀對應 `SKILL.md`，再依 skill 指示讀 references / knowledge。

不要在入口階段預先掃整個 `ai-system/skills/` 或 `ai-system/knowledge/` 目錄。

skill 承載流程導覽與知識入口，不放 executable script。所有 agent-facing executable 一律使用 `ai-system/approved-scripts/`。

## Skill Index

### system-audit

- 入口：`ai-system/skills/system-audit/SKILL.md`
- 適用：制度審計、規則衝突、制度制定、路由重排、分層整理、制度摩擦、agent 不遵守、安全網契約或安全邊界分類調整。
- 主要任務語彙：governance、audit、rules、conflict、routing、restructure、policy、safety net、hook、permission、sandbox、approved-scripts、制度、審計、規則、安全網。

### knowledge-maintenance

- 入口：`ai-system/skills/knowledge-maintenance/SKILL.md`
- 適用：整理知識、維護 skill index、修剪 references、檢查 repo 知識覆蓋度、維護環境 / context catalog、吸收 friction notes，或整理制度知識與安全網知識。
- 主要任務語彙：knowledge maintenance、skill cleanup、reference cleanup、coverage、friction notes、system knowledge、safety-net knowledge、知識治理、整理知識、制度知識、安全網知識。

## 新增 Workspace Skill 的判準

只有同時符合以下條件時才新增 skill：

1. 任務反覆出現，值得路由化。
2. 流程穩定到可以文件化。
3. skill 能降低後續查找、澄清或誤判成本。
4. skill 入口可以保持短小，細節放 references，而不是把 `SKILL.md` 寫成大型手冊。

instance-specific skill 可以登記在本 index，但若要重新發布 portable core，應清楚區分哪些是 portable、哪些是 adapter。
