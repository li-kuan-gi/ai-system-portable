# Codex Safety-Net Implementation Pack

本 pack 是 portable core 的一個 **Codex execution layer 實作範例**。

它很有用，但不是制度核心。portable core 定義「應該有安全網與 approved-scripts 契約」；本 pack 示範如何在 `~/.codex` 內落地：

- command prefix allow rules
- PermissionRequest hook
- sandbox / filesystem / hook config snippet
- trusted approved script directory

正式安全網契約見 `ai-system/safety-net/README.md`；本 pack 只是一種 Codex 實作方式。

## 包含內容

```text
implementation-packs/codex-safety-net/
  hooks/allow_trusted_script_permission.py
  rules/minimal.rules
  rules/devops-readonly.example.rules
  templates/config.snippet.toml
  scripts/install-safety-net.sh
  scripts/probe-hook.py
```

## 不包含內容

不得打包：

- `~/.codex/auth.json`
- `~/.codex/secrets/`
- sessions / logs / cache / shell snapshots
- 任何 token、password、cookie、bearer 或 credential 值
- 目標 workspace 的實際 host、namespace、客戶名或產品名

## 本機 secret store 慣例

若 Codex instance 需要長效本機工具憑證，可在目標機器自行建立：

```text
~/.codex/secrets/<service>/.env
```

這只是 Codex implementation pack 的 local-only 慣例，不是 portable core 規則；不得把實際檔案或任何值打包。

## 分層

| 層級 | 責任 |
|---|---|
| portable core | 語意 gate、制度、知識分層、approved-scripts 契約 |
| this pack | 把 approved-scripts/allow 轉成 Codex runtime 的自動 approval |
| instance adapter | 特定 workspace 的 helper、環境、工具與 secret store |

## 導入方式

建議先 dry-run：

```sh
implementation-packs/codex-safety-net/scripts/install-safety-net.sh \
  --workspace <WORKSPACE_ROOT> \
  --codex-home "$HOME/.codex" \
  --dry-run
```

確認輸出後再加 `--apply`：

```sh
implementation-packs/codex-safety-net/scripts/install-safety-net.sh \
  --workspace <WORKSPACE_ROOT> \
  --codex-home "$HOME/.codex" \
  --apply
```

安裝腳本會安裝 hook、`minimal.rules` 範本與 config snippet copy；若提供 `--codex-bin`，也會產生已替換實際路徑的 resolved config snippet，並在安全條件下寫入 `config.toml`。它不會修改 secrets、auth、sessions、logs 或 cache。

`--apply` 預設不覆寫既有 hook / rules。若目標檔已存在，腳本會拒絕執行。確認要更新時，先 dry-run，再使用：

```sh
implementation-packs/codex-safety-net/scripts/install-safety-net.sh \
  --workspace <WORKSPACE_ROOT> \
  --codex-home "$HOME/.codex" \
  --apply \
  --backup-existing
```

備份會放在：

```text
<CODEX_HOME>/backups/safety-net/<timestamp>-<pid>/
```

rollback 時，從該 backup directory 將 `hooks/` 與 `rules/` 內檔案複製回對應位置。

安裝後的 config snippet 會放在：

```text
<CODEX_HOME>/templates/portable-codex-safety-net.config.snippet.toml
```

若安裝時提供 `--codex-bin`，會額外產生：

```text
<CODEX_HOME>/templates/portable-codex-safety-net.config.resolved.toml
```

安裝器會依以下規則處理 `config.toml`：

- `config.toml` 不存在：直接用 resolved snippet 建立。
- `config.toml` 已存在且已引用同一 workspace 的 safety-net hook：保留不動。
- `config.toml` 已存在且是空檔：直接用 resolved snippet 建立內容。
- `config.toml` 已存在且有未知內容：預設停止；若使用 `--backup-existing`，會先備份再以 resolved snippet 取代。

若要人工合併，優先合併 resolved snippet，因為其中已帶入實際 workspace、`CODEX_HOME`、Codex binary 路徑與 runtime read path。不要在未備份時直接覆蓋既有 config。

可重跑 hook probe：

```sh
python3 implementation-packs/codex-safety-net/scripts/probe-hook.py \
  --workspace <WORKSPACE_ROOT>
```

## Hook 行為

`allow_trusted_script_permission.py` 只自動核准「單純執行 trusted script」：

- script 必須位於 `<WORKSPACE_ROOT>/ai-system/approved-scripts/allow`
- command 不可包含 `;`、`&&`、`|`、redirection、command substitution 等 shell composition
- 不自動核准 env assignment 或 shell variable expansion，例如 `FOO=bar helper`、`TOKEN=$TOKEN helper`
- 可接受無 option 的 shell / Python interpreter 執行，例如 `bash path/to/helper`、`python3 path/to/helper`
- 不自動核准 interpreter option，例如 `bash --noprofile helper`、`python3 -I helper`、`node --require=... helper`、`ruby -r... helper`、`perl -M... helper`
- cwd 若設定 `EXPECTED_CWD`，必須等於 workspace root

其他命令不輸出 decision，交回 Codex 正常 approval 流程。

## Rules profiles

- `minimal.rules`：只放跨 workspace 常用且低特定性的 Git 查詢 / 同步 prefix。
- `devops-readonly.example.rules`：GitHub 與 Kubernetes read-only prefix 範例。只有目標 workspace 確實使用這些工具時才合併。
