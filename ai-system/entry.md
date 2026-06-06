# Agent Entry

本檔是 portable core 的服務中性入口。任何 AI 服務的 project memory、agent instruction 或同等入口檔，都只應導向本檔，不要複製制度全文。

## 先讀

1. `ai-system/rules.md`

## 任務流程

任務路由以 `ai-system/skills/README.md` 為準。命中 skill 後，先讀對應的 `ai-system/skills/*/SKILL.md`，再依 skill 指示讀 references / knowledge。

## 按需深讀

- 邊界不清或高風險操作 -> `ai-system/constraints-detail.md`
- 安全網控制規範 -> `ai-system/safety-net.md`
- 制度 / 知識 / 安全網責任模型 -> `ai-system/governance/contracts.md`
- 制度審計、制度制定、規則衝突或治理原則 -> `ai-system/governance/principles.md`
- 延續前次對話、交接狀態或未完成決策 -> `ai-system/knowledge/context/agent-history.md`
- 使用者偏好、workspace 設定、AI service 設定或 launcher 設定 -> `ai-system/knowledge/context/agent-settings.md`
- 共享知識 -> `ai-system/knowledge/`
