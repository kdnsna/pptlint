# Ultimate PPT Master × DeckLint Proof Loop

这是 DeckLint v0.2 的公开真实案例，不是手工修改的演示数据。

| 指标 | Before | After | 变化 |
|---|---:|---:|---:|
| 总分 | 83 | 100 | +17 |
| Integrity | 70 | 100 | +30 |
| Readability | 70 | 100 | +30 |
| Accessibility | 95 | 100 | +5 |
| Critical | 9 | 0 | -9 |
| High | 92 | 0 | -92 |

比较结果：解决 103 项、持续存在 21 项、新增 3 项低置信提示，`high` 回归门禁通过。

修复内容：

1. Ultimate PPT Master 导出器补齐 Notes Master、notes theme、内容类型和 presentation relationship。
2. 清除模板默认作者/最后编辑者元数据。
3. 全部可见文字提升到 `ai-generated` 档案要求的 18pt，并定向修复字号提升后的局部溢出。
4. 封面标题进入语义标题识别区域，九页标题均由 DeckLint 推断成功。

持续存在的 21 项包括 9 个低置信阅读顺序提示、9 页主动保留的讲者备注隐私提示，以及字体、动效和重叠提醒。它们均不参与评分。

- [改造前 PPTX](before.pptx)
- [改造后 PPTX](after.pptx)
- [公开比较报告](https://kdnsna.github.io/decklint/proof-loop/comparison.html)
