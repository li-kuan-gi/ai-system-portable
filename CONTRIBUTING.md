# 貢獻指南

感謝你協助改善這套可攜 agent 制度。

## 範圍

Portable core 的契約應保持服務中性，所有內容必須保持 instance 中性。
請勿加入特定公司、客戶、產品、host、namespace、部署目標、account、
憑證或私人 workspace 設定。跨公司可重用的可選工具整合可以納入，但
不得內建 instance target 或私有狀態。

特定 workspace 的內容應放在該 workspace 自己的 adapter layer。特定 AI
服務的設定、hook、installer 與單一服務 bridge 應放在 `service-packs/` 或
`implementation-packs/`；跨服務且 instance-neutral 的 optional helper 可留在 core。

## Pull Request 前檢查

請先執行 `PORTABILITY.md` 的驗證清單，至少包含：

```sh
ai-system/approved-scripts/allow/portable-boundary-scan --root .
python3 scripts/probe-approved-helpers.py
```

也建議檢查 shell 與 Python 語法：

```sh
find ai-system/approved-scripts/allow ai-system/approved-scripts/prompt \
  -maxdepth 1 -type f -exec sh -n {} \;
python -m py_compile ai-system/approved-scripts/_lib/*.py
```

公開前請搜尋是否誤放私人資料：

```sh
rg -uuu -n "secret|token|password|passwd|api[_-]?key|client[_-]?secret|cookie|bearer|credential|private[_ -]?key|/home/|/Users/|@|namespace|host|客戶|公司|產品" .
```

合理命中應只會是通用規則文字、範例或公開文件連結。

## 撰寫原則

- 入口文件保持短小，負責導向正確層級。
- `ai-system/rules.md` 只放日常 agent 必須先知道的最小規則。
- 詳細邊界放在 `ai-system/constraints-detail.md`。
- 任務流程放在 `ai-system/skills/*/SKILL.md`。
- 已驗證事實與脈絡放在 `ai-system/knowledge/`。
- 不提交 secret、auth state、session dump、log 或 cache。

## Scripts

Agent-facing executable 應放在 `ai-system/approved-scripts/`。

`allow/` 只放範圍窄、可審查、適合自主執行的 helper。需要人工確認的 helper 應放在 `prompt/`。
