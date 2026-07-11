# DeckLint

> **面向 PowerPoint 的本地 PPT 质量基础设施。** 在交付前发现损坏、难读、栅格化、不一致、无障碍与隐私风险。

**Lighthouse for PowerPoint — deterministic, local and read-only.**

[![CI](https://github.com/kdnsna/decklint/actions/workflows/ci.yml/badge.svg)](https://github.com/kdnsna/decklint/actions/workflows/ci.yml)
[![Pages](https://github.com/kdnsna/decklint/actions/workflows/pages.yml/badge.svg)](https://kdnsna.github.io/decklint/)
[![License: MIT](https://img.shields.io/badge/license-MIT-10233f.svg)](LICENSE)

DeckLint 将 `.pptx` 转换为可离线打开的 HTML 报告和稳定 JSON 合同。它不上传演示文稿、不调用模型，也不修改源文件。

## 从审计到改进证明

```text
PPTX → audit → findings → 局部重做 → audit → compare
```

v0.2 新增 `compare`：比较改造前后的两份审计报告，明确列出已解决、持续存在和新增问题，并可在 CI 中阻断回归。

## 通过 GitHub Release 运行

在 PyPI Trusted Publishing 正式完成前，使用 Release wheel：

```bash
uvx --from https://github.com/kdnsna/decklint/releases/download/v0.2.0/decklint-0.2.0-py3-none-any.whl \
  decklint audit quarterly-review.pptx --profile ai-generated
```

生成：

- `decklint-report.html`：中文可视化报告，完全离线。
- `decklint-report.json`：CI、Agent 与第三方工具可消费的稳定数据。

比较两次审计：

```bash
decklint compare before-report.json after-report.json \
  --output decklint-comparison \
  --fail-on-regression high
```

退出码：`0` 表示通过，`1` 表示质量或回归门禁失败，`2` 表示输入或运行错误。

## 可验证示例

- [真实 Proof Loop：49→100，解决 103 项，新增 0 项](https://kdnsna.github.io/decklint/)：Ultimate PPT Master 生成、DeckLint 审计、定向修复并比较。
- [前后比较报告](https://kdnsna.github.io/decklint/proof-loop/comparison.html)：critical 9→0、high 92→0，`high` 回归门禁通过。
- [正常 Deck 报告](examples/reports/good-deck.html)：原生文字、可读字号、无高置信交付阻断。
- [问题 Deck 报告](examples/reports/bad-deck.html)：全页栅格图、缺少 alt text、小字号和显式低对比度。
- [审计 JSON Schema](schema/decklint-report-v1.schema.json)：`decklint-report/v1`。
- [比较 JSON Schema](schema/decklint-comparison-v1.schema.json)：`decklint-comparison/v1`。

案例文件位于 [`examples/proof-loop/`](examples/proof-loop/)。持续存在的 18 项为 9 个低置信阅读顺序提示和 9 页主动保留的讲者备注隐私提示，均不扣分；报告没有隐藏这些风险。

## 审计范围

| 维度 | 确定性检查 |
|---|---|
| 完整性 | ZIP/XML、包关系、媒体、空演示文稿 |
| 可读性 | 显式字号、越界文字、显式低对比度、密度提示 |
| 可编辑性 | 全页栅格图覆盖与原生对象比例 |
| 一致性 | 字体异常值、颜色异常值、重复布局指纹 |
| 无障碍 | 标题、图片 alt text、阅读顺序风险 |
| 隐私 | 作者信息、批注、隐藏页、讲者备注、外部关系 |

高置信 finding 参与评分和门禁；低置信启发式只作提示，不扣分、不阻断 CI。隐私风险单独展示，不参与总分。

## 透明评分

五个维度从 100 分开始。高置信 finding 按 critical 30、高 15、中 5、低 1 扣分，同一规则最多扣 30 分。总分权重为：完整性 30%、可读性 25%、可编辑性 20%、一致性 15%、无障碍 10%。完整性 critical 将总分上限限制为 49。

JSON 和 HTML 都公开每项 finding 的请求扣分、实际扣分、限额原因、加权计算和完整性上限状态。

## 渲染

- `wireframe`：直接根据 OOXML 生成结构预览，所有环境可用。
- `auto`：检测到 LibreOffice 时使用隔离临时配置生成真实页面预览，失败后无损降级为 wireframe。
- `libreoffice`：严格模式；找不到或渲染失败时返回退出码 `2`。

## GitHub Action

```yaml
- uses: kdnsna/decklint@v0
  with:
    path: decks/quarterly-review.pptx
    profile: ai-generated
    fail-on: high
    min-score: "80"
```

即使质量门禁失败，Action 仍上传 HTML 和 JSON 报告。

## 产品边界

DeckLint v0.2 仍然只读。它不是 PPT 生成器、视觉编辑器、云服务或自动修复工具，也不判断论点是否真实、视觉风格是否“好看”。生成和局部重做可以交给 Ultimate PPT Master，DeckLint 只提供可追踪证据。

## 开发

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
PYTHONPATH=src pytest
ruff check src tests tools
python -m build
```

公开合成样本位于 `tests/fixtures/corpus/`；仓库不提交私有业务演示文稿。

## English summary

DeckLint audits PowerPoint files locally and does not upload or modify the source. It produces deterministic offline HTML and JSON reports. Version 0.2 adds before/after comparison with regression gates.

After the PyPI release is verified, the canonical command will be:

```bash
uvx decklint audit quarterly-review.pptx
```

## License

MIT。参见 [第三方许可证说明](THIRD_PARTY_NOTICES.md)。

## 致谢

DeckLint 的原生对象检查源于 [Ultimate PPT Master](https://github.com/kdnsna/ultimate-ppt-master-skill) 的质量门禁实践。DeckLint 只提取中立检查层，不引入生成器、模板、Bridge 或工作流合同。
