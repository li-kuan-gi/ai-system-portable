# Agent Settings

本檔存放 agent 可讀、可被任務引用的 workspace 設定與使用偏好。

portable package 中本檔應保持初始化狀態。導入到實際 workspace 後，才由 instance adapter 補上實際設定。

## 讀取時機

- 任務需要知道使用者偏好的語言、輸出形式、操作習慣或安全偏好時，先讀本檔。
- 任務需要知道目前 workspace 的非敏感 local path、AI service home、launcher command 或設定來源時，先讀本檔。
- 任務結果依賴 service-specific 設定時，先查本檔，再查對應 service pack 或實際設定檔。

## 寫入規則

- 只寫 agent 可以安全閱讀與引用的設定。
- 設定應標明來源與查證狀態，例如使用者指定、本機檢查、service config 或 adapter 文件。
- 不得寫入 secret、token、password、cookie、credential、private key、完整 auth state 或 session cache。
- 不要把快速變動的 runtime state 寫成長期設定。
- 若設定只對特定 AI 服務有效，應標明服務名稱與適用範圍。

## 使用者偏好

目前沒有使用者偏好。

## Workspace 設定

目前沒有 workspace 設定。

## AI Service 設定

目前沒有 AI service 設定。

導入特定 AI service 後，可以在本節記錄 service-managed storage 的實際位置，例如設定檔、對話 sessions、history、memory、log 與禁止讀取的 auth / secret 路徑。

## Local Path 與 Launcher

目前沒有 local path 或 launcher 設定。
