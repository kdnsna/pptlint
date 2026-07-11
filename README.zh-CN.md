# PPTLint

> **AI 生成 PPT 后，发出去之前检查一次。**

[English](README.md) · [在线示例](https://kdnsna.github.io/pptlint/) · [修改前后对比](https://kdnsna.github.io/pptlint/proof-loop/comparison.html)

[![存在问题的 AI PPT 与修改后可交付版本对比](site/assets/pptlint-before-after-hero.png)](https://kdnsna.github.io/pptlint/proof-loop/comparison.html)

AI 工具可以很快生成 PowerPoint，但也可能留下缺失文件、文字被裁掉、文字框互相遮挡、字号过小、整页变成图片、讲者备注、批注或个人信息。

PPTLint 在你的电脑上检查 `.pptx`，直接给出三种结果：

- **可以交付**：没有发现高置信的严重问题。
- **建议检查**：文件可以打开，但请人工确认报告中指出的页面。
- **暂勿交付**：先解决报告列出的必要修改，再发送文件。

PPTLint 不上传 PPT、不调用 AI 模型，也不修改源文件。

如果需要先生成或修复 PPT，请使用 [Ultimate PPT Master](https://github.com/kdnsna/ultimate-ppt-master-skill)，再用 PPTLint 做独立交付检查。

## 直接交给 Agent

把下面这句话发送给 Codex、Claude Code 或其他编程 Agent：

```text
请安装 PPTLint，并检查这个 AI 生成的 PPT 是否适合交付。
优先告诉我必须修改的页面，以及在 PowerPoint 中应该怎样操作。
```

## 自己运行

直接从 PyPI 安装并运行：

```bash
uvx pptlint check output.pptx --profile ai-generated
```

运行后生成：

- `pptlint-report.html`：普通用户可以离线打开；
- `pptlint-report.json`：供 Agent 和自动化工具读取。

报告第一屏先显示是否可以交付，再列出最多三项最应优先处理的修改。数字分数只用于观察同一份 PPT 修改前后的变化，不代表整体审美水平。

## 查看真实案例

- [可以交付的示例](examples/reports/good-deck.html)
- [存在问题的示例](examples/reports/bad-deck.html)
- [真实可编辑 PPT 修改前后对比：49 → 100](https://kdnsna.github.io/pptlint/proof-loop/comparison.html)
- [修改前 PPTX](examples/proof-loop/before.pptx) 与 [修改后 PPTX](examples/proof-loop/after.pptx)
- [五个 AI PPT 项目的公开检查方法](https://kdnsna.github.io/pptlint/benchmark/)

## 修改后再次检查

保留原文件，修改独立副本，然后比较两次结果：

```bash
pptlint check before.pptx --output before
pptlint check after.pptx --output after
pptlint compare before.json after.json --output comparison
```

比较报告会分别显示已经解决、仍需处理和修改后新增的问题。

## GitHub Actions

```yaml
- uses: kdnsna/pptlint@v0
  with:
    path: output.pptx
    profile: ai-generated
    renderer: wireframe
```

即使检查没有通过，HTML 和 JSON 报告仍会上传。

## 检查内容

| 你关心的问题 | PPTLint 检查什么 |
|---|---|
| 文件能否正常打开 | PPTX 内部文件、媒体、页面列表和实际渲染 |
| 放映时是否容易出错 | 越界文字、明显遮挡、裁切风险、字号、对比度和页面比例 |
| 后续是否方便修改 | 整页图片，以及原生文字、表格、图表和形状比例 |
| 文件能否安全外发 | 备注、批注、隐藏页、作者信息、外部文件和链接 |

低置信提示只会显示为“建议检查”，不会阻止交付。PPTLint 不判断 PPT 是否美观、论点是否正确或内容是否有说服力。

## 开发者接口

- 当前报告：[`pptlint-report/v2`](schema/pptlint-report-v2.schema.json)
- 旧版报告：[`decklint-report/v1`](schema/decklint-report-v1.schema.json)
- 修改前后比较：[`decklint-comparison/v1`](schema/decklint-comparison-v1.schema.json)
- 退出码 `0`：完成；`1`：需要修改；`2`：文件或运行错误。

旧 `decklint` 命令保留到 v0.4，旧报告仍可继续比较。

PPTLint 本地运行、只读、不调用模型、不收集使用数据，采用 MIT 许可证。
