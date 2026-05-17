# Context Knowledge

本目錄放 workspace-level 事實，例如：

- 架構概覽
- 環境 catalog
- service 與 repo 對照
- approved lookup route
- 共享操作邊界
- agent 可讀的歷史對話摘要與交接狀態
- agent 可讀的 workspace / AI service 設定與使用偏好

portable core 不預設任何 instance-specific catalog；導入真實 workspace 時再由 adapter 補上。

初始化檔案：

- `agent-history.md`：放歷史對話摘要、交接狀態、未完成決策與待辦。
- `agent-settings.md`：放可安全讓 agent 讀取的使用偏好、workspace 設定、AI service 設定與 local launcher 資訊。

這些檔案在 portable package 中應保持空白初始化內容；實際內容由導入後的 instance adapter 或 agent 依證據補上。
