# Roadmap

PPTLint 保持窄边界：在发送或演示前检查 PowerPoint，并用可复现证据说明问题和变化。

## v0.3 — 普通用户可以直接理解的交付检查

- `pptlint check`、可以交付／建议检查／暂勿交付三种结果。
- 最多三项优先修改，以及 PowerPoint 中的具体操作步骤。
- PPTLint 新主仓；DeckLint 保留旧 Action 兼容入口。

## v0.4 — 一条命令完成真实复检闭环

- `pptlint proof before.pptx after.pptx` 同设置检查修改前后文件。
- 一次生成修改前、修改后和完整对比三组 HTML/JSON 证据。
- 终端直接显示已处理、仍存在、新增以及新增高把握问题数量。
- 继续保持本地、只读、不上传、不调用模型的产品边界。

## v0.5 — 可信检查

- 按现场汇报、屏幕阅读和文档型演示校准字号与密度。
- 消除亚像素边界和备注关系造成的错误阻断。
- 把同一根因产生的大量对象提醒合并为问题组。

## v0.1 — 只读审计基础

- 本地 CLI、确定性 JSON、离线 HTML、透明评分和 GitHub Action。
- 不调用模型、不上传、不修改源文件。

## v0.2 — Proof Loop

- `pptlint compare` 前后报告比较。
- `decklint-comparison/v1`、中文离线比较报告和回归门禁。
- AI 生成页面的原生语义标题识别。
- Ultimate PPT Master 真实修复闭环、Pages 案例和公开证据资产。

## 后续候选

- 可选策略文件与品牌字体、色彩检查。
- SARIF 与 PR 注释。
- 有跨平台公开样本支持的更多 renderer。
- 仅在诊断误报率与用户信任得到验证后，研究安全修复副本。

PyPI 使用无 token 的 Trusted Publishing，发布流程见 `docs/publishing.md`。
