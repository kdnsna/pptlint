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

## v0.6 — 高级交付检查

- 展示真实可编辑对象、媒体、文件体积、字体和动态效果交接事实。
- 检查大文件、重复媒体、动画和音视频跨软件风险。
- 支持企业字体、颜色、字号、隐私和无障碍 YAML 策略。
- 输出可直接交给 Coding Agent 的只读修复简报。

## v0.7 — 交付案例实验室

- 发布 12 个完整前后对比，覆盖现场可读性、换电脑稳定性、可编辑交接、隐私、完整性、体积和团队规范。
- 每个案例公开规则、处理边界和复检命令，明确 100 分不等于审美满分。
- 将可控情境演示与热门开源 AI PPT 的公开样本实测分开展示。
- 首页、案例页和真实 Proof Loop 形成可验证的证据路径。

## v0.7.1 — 发布与证据一致性

- 使用当前版本重新生成公开 Proof Loop，所有宣传数字以 comparison JSON 为准。
- 同步 PyPI、GitHub Release、浮动 `v0` Action 标签与仓库版本。
- 补齐版本命令、Action 场景/语言/策略输入和中文报告。

## v0.8 — 开放修复计划

- 为全部问题组生成稳定、机器可读的修复任务，而不是只输出前三项建议。
- 支持通用 Agent、Ultimate、PowerPoint Copilot 和人工 PowerPoint 适配说明。

## v0.9 — 显式隐私清理副本

- 只在用户逐项授权后清理独立副本中的个人信息、批注和讲者备注。
- 生成执行收据和修改后验证，不覆盖源文件。

## v1.0 — 本地拖放式应用

- 在仅绑定本机的页面中完成拖入、检查、选择清理、下载副本和复检。

## v0.1 — 只读审计基础

- 本地 CLI、确定性 JSON、离线 HTML、透明评分和 GitHub Action。
- 不调用模型、不上传、不修改源文件。

## v0.2 — Proof Loop

- `pptlint compare` 前后报告比较。
- `decklint-comparison/v1`、中文离线比较报告和回归门禁。
- AI 生成页面的原生语义标题识别。
- Ultimate PPT Master 真实修复闭环、Pages 案例和公开证据资产。

## 后续候选

- SARIF 与 PR 注释。
- 有跨平台公开样本支持的更多 renderer。
- PowerPoint Windows、PowerPoint Mac、WPS 和 LibreOffice 目标环境档案。

PyPI 使用无 token 的 Trusted Publishing，发布流程见 `docs/publishing.md`。
