# AI 服務可攜策略

portable core 的目標是讓同一套制度能被不同 AI 服務消費。

## 分層

| 層級 | 是否通用 | 說明 |
|---|---:|---|
| `ai-system/` portable core | 是 | 中性入口、制度 / 知識 / 安全網契約、規則、治理、workspace skill 路由 |
| `templates/` | 是 | skill 模板 |
| `service-packs/` | 否 | 特定 AI 服務入口與設定，例如 Codex、Claude Code |
| `implementation-packs/` | 否 | 特定 runtime / launcher 的安全網實作，例如 permission hook 或 sandbox config |
| instance adapter | 否 | 特定公司、產品、環境、issue tracker、log platform、API |

## 對任一 AI 服務的共同要求

導入時只需要讓該服務知道：

1. 先讀 workspace 的 service entry，或直接讀 `ai-system/entry.md`。
2. service entry 只應指向 `ai-system/entry.md`，不複製制度全文。
3. `ai-system/entry.md` 指向 `ai-system/rules.md`。
4. 任務路由由 `ai-system/skills/README.md` 管理。
5. 可執行 helper 的正式入口是 `ai-system/approved-scripts/allow/` 與 `prompt/`。
6. 安全網契約由 `ai-system/safety-net.md` 定義；service-specific permission / hook / sandbox 只是實作。
7. secrets 不進 workspace，不進 `.md`，不進 git-tracked path。
8. service-specific permission table 不是制度真相來源。

## 新增 Service Pack 的最小內容

```text
service-packs/<service>/
  README.md
  templates/
    <service-entry-file>
    <service-settings-template>
```

若該服務支援 hook / permission / command / skill，可再加：

```text
service-packs/<service>/
  hooks/
  commands/
  skills/
  scripts/
```

## 不要做的事

- 不要把 service-specific 設定寫回 portable `rules.md`。
- 不要要求日常 agent 分辨多種 service 的 hidden skill 目錄。
- 不要把某服務的 permission table 當成制度本體。
- 不要把 secrets 或 auth state 放進 service pack。
