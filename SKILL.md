---
name: pptlint
description: Use when a user wants to check whether an existing PowerPoint PPTX is safe and ready to present, send, publish, or hand off.
---

# PPTLint

检查已有 `.pptx` 是否适合交付。PPTLint 只读取文件，不上传、不调用模型，也不修改原文件。

## 第一次检查

```bash
pptlint check input.pptx \
  --profile ai-generated \
  --renderer auto \
  --output pptlint-report
```

先读取 `pptlint-report.json`：

- `readiness.status == blocked`：存在交付前必须解决的问题。
- `readiness.status == review`：文件可以打开，但仍有内容需要人工确认。
- `readiness.status == ready`：未发现会阻止交付的高置信问题。
- `priorityActions`：最多三项最先处理的修改。

向用户说明页码、实际影响和 `fixSteps`。不要先展示内部规则编号或总分。

## 修改后复检

生成独立副本并再次运行 `pptlint check`。如需证明修改前后的变化：

```bash
pptlint compare before.json after.json \
  --output pptlint-comparison \
  --fail-on-regression high
```

将 `resolved` 解释为“已经解决”，`persistent` 解释为“仍需处理”，`new` 解释为“修改后新增”。

## 退出码

- `0`：检查完成，未达到失败条件。
- `1`：存在必须修改的问题或指定检查条件未通过。
- `2`：文件损坏、输入无效或运行失败。

## 边界

- Do not modify the source PPTX.
- 未经用户明确要求，不上传 PPTX 或报告。
- 低置信提示只能描述为“建议检查”，不能称为确定错误。
- 以 CLI 和公开 JSON 文件为准，不复制检测逻辑。
