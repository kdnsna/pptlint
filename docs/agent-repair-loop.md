# 修改与复检

PPTLint 只负责检查与比较，不修改 PowerPoint。生成 Agent 必须保留源文件，并输出独立修复副本。

## 1. 审计初稿

```bash
pptlint check before.pptx \
  --profile ai-generated \
  --renderer auto \
  --fail-on none \
  --output before-report
```

## 2. 建立逐页修复清单

读取 `before-report.json` 的 `findings[]`，保留：

- `id`
- `slide_index`
- `rule_id`
- `confidence`
- `evidence`
- `remediation`

高置信 finding 可以作为修复依据；低置信 finding 必须标记为人工复核项。

## 3. 生成独立副本

生成器只修改被 finding 或人工 QA 明确命中的页面，输出 `after.pptx`，不得覆盖 `before.pptx`。

## 4. 复审并比较

```bash
pptlint proof before.pptx after.pptx \
  --profile ai-generated \
  --renderer auto \
  --lang zh-CN \
  --output comparison \
  --fail-on-regression high
```

该命令会使用相同设置生成 `comparison-before`、`comparison-after` 和 `comparison` 三组 HTML/JSON。若已经分别生成两份 JSON，仍可使用 `pptlint compare before-report.json after-report.json`。

只有 `gate.passed == true`、没有新的 high/critical finding 且目标维度未下降时，才能将改造描述为规则证据支持的改善。`resolved` 只表示对应提醒在修改后不再报告，不代表审美完美或绝对零风险。人工视觉润色必须单独列出。
