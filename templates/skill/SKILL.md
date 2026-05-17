# <Skill Name>

## 觸發

以下情況使用本 skill：

- <任務訊號 1>
- <任務訊號 2>

## 任務

說明這個 skill 幫助 agent 做什麼。入口保持短小；細節放在 `references/`。

## 邊界

- read-only actions：
- prompt / confirmation actions：
- forbidden actions：
- fallback skill：

## 必要 context

執行前先確認：

- 目標 repo / file / service：
- 相關環境或 runtime target：
- 成功條件：
- 限制與已知風險：

## 流程

1. 確認任務命中本 skill。
2. 只讀必要的 reference files。
3. 有證據後才把現況寫成事實。
4. 有 approved helper 時優先使用。
5. 關鍵依賴失效時及早回報 blocker。

## References

- `references/workflow.md`

## 產出格式

```markdown
## 摘要
- 結果：
- 證據：
- 風險 / 不確定性：
- 下一步：
```

