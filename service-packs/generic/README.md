# Generic Service Pack

用於尚未提供專屬 pack 的 AI 服務。

## 最小導入契約

讓該服務在 workspace 啟動時讀到以下內容：

1. 先讀 `ai-system/entry.md`，或讀會導向它的服務入口檔。
2. `ai-system/entry.md` 指向 `ai-system/rules.md`。
3. 任務路由由 `ai-system/skills/README.md` 管理。
4. 高風險或邊界模糊時讀 `ai-system/constraints-detail.md`。
5. 制度審計或治理時讀 `ai-system/governance/principles.md`。
6. 可執行 helper 只從 `ai-system/approved-scripts/allow/` 或 `prompt/` 進入。

## 需要自行補的服務功能

- 該服務的 project memory / instruction file
- 該服務的 settings / permissions
- 該服務的 hook / guardrail 機制
- skill / command / tool bridge
- secret store 與 sandbox 策略
