# Implementation Packs

本目錄放「有用但不是 portable core」的實作包。

portable core 定義制度契約；implementation pack 提供某個 runtime、launcher、sandbox、hook 或工具生態的落地方式。

## 原則

- implementation pack 可打包，但必須和 core 分開。
- 不得包含 auth、secret、token、password、session history、log、cache 或使用者私有狀態。
- 應提供安裝說明、dry-run 或人工合併方式。
- 應使用 placeholder，不綁定原 workspace 絕對路徑。
- 若 pack 只適用特定 runtime，需在 README 寫明。

## Packs

| Pack | 用途 |
|---|---|
| `codex-safety-net/` | Codex `~/.codex` execution layer 範例：PermissionRequest hook、minimal rules、optional rules profiles、config snippet |
