# Roadmap

DeckLint 保持窄边界：在交付前检查 PowerPoint，并用可复现证据说明问题和变化。

## v0.1 — 只读审计基础

- 本地 CLI、确定性 JSON、离线 HTML、透明评分和 GitHub Action。
- 不调用模型、不上传、不修改源文件。

## v0.2 — Proof Loop

- `decklint compare` 前后报告比较。
- `decklint-comparison/v1`、中文离线比较报告和回归门禁。
- AI 生成页面的原生语义标题识别。
- Ultimate PPT Master 真实修复闭环、Pages 案例和公开证据资产。

## 后续候选

- `.decklint.yml` 策略覆盖与品牌字体/色彩规则。
- SARIF 与 PR 注释。
- 有跨平台公开样本支持的更多 renderer。
- 仅在诊断误报率与用户信任得到验证后，研究安全修复副本。

PyPI 使用无 token 的 Trusted Publishing，发布流程见 `docs/publishing.md`。
