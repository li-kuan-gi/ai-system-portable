---
name: safety-net-sync
description: 檢查或更新 AI 服務的 hooks、permissions、sandbox、rules 與 approved scripts，使服務實作忠實落實 safety-net spec。
---

# Safety-Net Sync

## 流程

1. 讀 `ai-system/safety-net.md`，把它當唯一 policy spec。
2. 列出目前在場的服務實作：
   - portable source：`implementation-packs/` 與 `service-packs/`
   - instance：依目標 service pack / implementation pack 的文件找到實際安裝位置
   - approved allow/prompt entrypoints
3. 逐條比對該攔、該 prompt、該 allow 的行為。
4. 實作落後 spec 時更新；實作越權或 spec 有問題時先回 system-audit。
5. 執行 config syntax、hook probes 與低風險 smoke checks。
6. 確認 package 未納入、instance 更新未讀取或覆寫 auth、sessions、history、cache、logs、sqlite 或 secrets。

改變 agent 執行邊界前，先說明目的、影響、驗證與 recovery。
