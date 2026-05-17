# 安全政策

本 repository 不應包含憑證、auth state、session history、log、cache、客戶資料、內部 host、部署目標或私人 workspace 設定。

## 回報安全問題

若 GitHub private security advisory 可用，請優先使用該管道回報。若尚未啟用 private advisory，請透過維護者可用的最低公開程度管道聯絡，並避免在公開 issue 中貼出 secret 或可利用細節。

## Secret 處理

若 secret 被提交：

1. 立即撤銷或輪替該憑證。
2. 從 repository 移除 secret。
3. 將已 clone 的副本與 fork 視為可能已暴露。
4. 補上或收緊檢查，避免同類 secret 再次被提交。

不要只依賴重寫 git history 作為唯一補救措施。
