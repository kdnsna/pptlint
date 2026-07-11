---
name: decklint
description: Audit and compare PowerPoint PPTX quality reports without uploading or modifying the source file.
---

# DeckLint

当用户要求检查、审计、QA、验证或比较 `.pptx` 时使用 DeckLint。

## 审计

优先使用已安装命令：

```bash
decklint audit input.pptx --output decklint-report
```

AI 生成且应保留原生可编辑对象的演示文稿使用：

```bash
decklint audit input.pptx \
  --profile ai-generated \
  --renderer auto \
  --output decklint-report
```

读取 `decklint-report.json`，按 `slide_index`、`rule_id`、`evidence` 与 `remediation` 建立逐页修复清单。低置信 finding 只作提示。

## 修复后比较

重新审计独立的修复副本，再比较两份 JSON：

```bash
decklint compare before-report.json after-report.json \
  --output decklint-comparison \
  --fail-on-regression high
```

- `resolved`：改造前存在、改造后消失。
- `persistent`：同一规则仍在同一页出现。
- `new`：改造后新增。
- `gate.passed`：回归门禁是否通过。

## 退出码

- `0`：通过。
- `1`：质量门禁或回归门禁失败。
- `2`：输入无效或运行失败。

## 安全边界

- Do not modify source PPTX.
- 不上传 PPTX 或报告，除非用户明确要求。
- 不修改源 PPTX；生成器应输出独立修复副本。
- 不把启发式 warning 描述为已证明的设计缺陷。
- 不复制 DeckLint 规则逻辑；以 CLI 和 JSON Schema 为唯一合同。
