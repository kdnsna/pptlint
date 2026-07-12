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
  --lang zh-CN \
  --output pptlint-report
```

先读取 `pptlint-report.json`：

- `readiness.status == blocked`：存在交付前必须解决的问题。
- `readiness.status == review`：文件可以打开，但仍有内容需要人工确认。
- `readiness.status == ready`：未发现会阻止交付的高置信问题。
- `priorityActions`：最多三项最先处理的修改。
- `deliveryChecklist`：文件打开、现场可读、后续可改、隐藏内容四项交付体检。
- `affectedSlides`：同一类问题涉及的页面；不要把相同动作重复列出。

向用户说明页码、实际影响和 `fixSteps`。不要先展示内部规则编号或总分。

普通用户希望检查后直接查看报告时，可运行 `pptlint start input.pptx --lang zh-CN`。遇到安装或渲染问题时先运行 `pptlint doctor --json`，不要要求用户上传原 PPT。

完整 HTML/JSON 可能包含页面预览、文字和属性。需要外发诊断结果时，使用 `--report-mode shareable`，并再次确认没有业务敏感信息。

如需套用企业交付规范：

```bash
pptlint policy init company-ppt.yml
pptlint check input.pptx --policy company-ppt.yml --lang zh-CN
```

策略例外必须包含业务理由，可限制具体页面并设置到期日。不要为了通过检查而添加无理由或永久例外。

如需交给 Coding Agent 修改：

```bash
pptlint plan pptlint-report.json --output repair-brief.md
```

## 修改后复检

生成独立副本后，用同一组设置检查修改前后文件并生成完整证据：

```bash
pptlint proof before.pptx after.pptx \
  --profile ai-generated \
  --lang zh-CN \
  --output pptlint-comparison \
  --fail-on-regression high
```

命令会写出修改前、修改后和对比三组 HTML/JSON。将 `resolved` 解释为“修改后不再报告”，`persistent` 解释为“仍需人工确认”，`new` 解释为“修改后首次报告”。已经存在两份报告时仍可使用 `pptlint compare`。

## 退出码

- `0`：检查完成，未达到失败条件。
- `1`：存在必须修改的问题或指定检查条件未通过。
- `2`：文件损坏、输入无效或运行失败。

## 边界

- Do not modify the source PPTX.
- 未经用户明确要求，不上传 PPTX 或报告。
- 低置信提示只能描述为“建议检查”，不能称为确定错误。
- 以 CLI 和公开 JSON 文件为准，不复制检测逻辑。
