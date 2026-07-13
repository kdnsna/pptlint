# PPTLint

**PPT 做完以后，别急着发。** 你电脑上看不出来的问题，往往会在领导、客户或会议室的电脑上暴露。

[产品首页](https://kdnsna.github.io/pptlint/) · [案例实验室](https://kdnsna.github.io/pptlint/lab/) · [真实 Proof Loop](https://kdnsna.github.io/pptlint/proof-loop/comparison.html) · [English](README.en.md)

![PPTLint：PowerPoint 交付前质量检查](site/assets/readme-hero.svg)

[![CI](https://github.com/kdnsna/pptlint/actions/workflows/ci.yml/badge.svg)](https://github.com/kdnsna/pptlint/actions/workflows/ci.yml)
[![Pages](https://github.com/kdnsna/pptlint/actions/workflows/pages.yml/badge.svg)](https://kdnsna.github.io/pptlint/)
[![PyPI](https://img.shields.io/pypi/v/pptlint.svg)](https://pypi.org/project/pptlint/)
[![License](https://img.shields.io/badge/license-MIT-10233f.svg)](LICENSE)

| 30 秒看懂 | 12 个案例 | 真实前后对比 |
|---|---|---|
| [产品首页](https://kdnsna.github.io/pptlint/) | [案例实验室](https://kdnsna.github.io/pptlint/lab/) | [83 → 100 Proof Loop](https://kdnsna.github.io/pptlint/proof-loop/comparison.html) |

## 它解决的不是“好不好看”，而是“能不能放心发”

- **会上出丑**：字体替换后标题换行，最后一行被截掉，两个文本框压在一起。
- **换电脑变样**：特殊字体、外部 Excel、音视频或动画离开原电脑后失效。
- **别人无法接手**：整页其实是一张图，对方想改一个数字也选不中。
- **内部内容被带出去**：讲者备注、隐藏页、批注、作者信息或本地链接仍留在文件里。
- **文件本身不稳**：包内对象缺失、重复媒体过多，打开时弹出修复或等待很久。

PPTLint 默认在本机只读检查 `.pptx`，生成离线 HTML 与 JSON 报告。它**不上传文件、不调用模型、不收集遥测数据，也不修改源文件**。只有你逐项授权清理时，它才会写入一份新的副本。

## 一分钟开始

把这句话发给 Codex、Claude Code 或其他 Coding Agent：

```text
请安装 PPTLint，检查这份 PowerPoint 是否适合发给客户。
按“必须处理、需要确认、建议查看”告诉我先改哪几页，
再生成完整修复任务。不要覆盖原文件，修改后重新检查。
```

或者直接运行：

```bash
uvx pptlint check output.pptx --scenario present --lang zh-CN
```

不想看命令，可以启动只在本机运行的拖放页面：

```bash
uvx --refresh pptlint app
```

它会在随机的 `127.0.0.1` 端口打开中文页面。检查后，每项问题都会同时给出 PowerPoint 桌面版人工步骤。真实旧稿的视觉修改目前坚持人工优先：在原生、保真的对象级编辑链路完成前，不再把整份 PPT 导入后重新导出来冒充“一键局部优化”，避免母版、透明背景、组合对象、链接和未选页被破坏。

文件只进入本机临时目录，关闭后删除；页面不会请求外部字体、统计或云端模型。你仍可复制完整任务交给助手分析，但视觉修改不会自动重导出源文件；PPTLint 只自动生成不改变页面布局的安全清理副本。

修改后的文件复检时，规则通过只是辅助证据。页面会要求先在 PowerPoint/WPS 中确认修改页没有黑底、缺字、丢链接、错位或异常换行；没有这一步，不生成 Verified 凭证。

## 从发现问题到复检通过

PPTLint 已有的完整流程是：

1. **检查**：告诉你现在能不能交付，以及问题在哪一页。
2. **生成修复任务**：把全部问题分给 PPTLint、PowerPoint、人工或 Agent。
3. **授权清理副本**：只清理你明确勾选的作者信息、批注或讲者备注。
4. **修改复杂问题**：版式、隐藏页、外部链接和整页图片仍由人或 Agent 判断。
5. **重新检查**：对比哪些已处理、哪些仍存在、哪些是修改后新出现的。
6. **验证交付**：只有全部修复任务通过验证，才生成 `PPTLint Verified` 凭证。

PPTLint 不会把“发现问题”伪装成“已经修好”，也不会为了得到高分擅自改动内容。

## 真实证据：83 → 100，但不是“零问题”

公开 Proof Loop 使用同一份 9 页可编辑 PPT，按当前版本重新检查：

| 指标 | 结果 |
|---|---:|
| 检查分数 | **83 → 100** |
| 已处理的高置信问题 | **103 项** |
| 仍需人工确认的低置信提醒 | **21 项** |
| 修改后新增的低置信提示 | **3 项** |
| 修改后新增的高置信问题 | **0 项** |

因此，修改后虽然是 100 分，结论仍是**建议确认**，报告中仍有 24 项低置信提醒。100 分只是当前规则下没有高置信扣分项，不是审美满分，也不是绝对零风险。

- [打开完整前后对比](https://kdnsna.github.io/pptlint/proof-loop/comparison.html)
- [下载修改前 PPTX](examples/proof-loop/before.pptx)
- [下载修改后 PPTX](examples/proof-loop/after.pptx)
- [查看机器可读 comparison JSON](site/proof-loop/comparison.json)

案例实验室还持续验证 33 份来自 4 个公开项目族的 PPTX，共 383 页；当前固定样本全部运行成功，修复任务覆盖率为 100%。这些是兼容性样本，不是审美排名，也不代表 PPTLint 能自动修复全部问题。

## 常用命令

检查并打开报告：

```bash
uvx pptlint start output.pptx --scenario present --lang zh-CN
```

生成完整修复计划：

```bash
uvx pptlint plan pptlint-report.json --format json --output repair-plan.json
uvx pptlint plan pptlint-report.json --adapter generic-agent --lang zh-CN --output repair-brief.md
```

明确授权清理一份独立副本：

```bash
uvx pptlint fix input.pptx \
  --output input.delivery.pptx \
  --apply clear-personal-metadata \
  --apply remove-comments \
  --apply remove-speaker-notes
```

比较修改前后：

```bash
uvx pptlint proof before.pptx after.pptx \
  --scenario present --lang zh-CN --output comparison
```

安全分享报告（隐藏文件名、页面标题、预览和对象级证据）：

```bash
uvx pptlint check output.pptx --lang zh-CN \
  --report-mode shareable --output pptlint-safe
```

排查安装与渲染环境：

```bash
uvx pptlint doctor
```

## 结果怎么理解

| 结论 | 该做什么 |
|---|---|
| 可以交付 | 没发现高置信交付问题，仍应做最终人工预览 |
| 建议确认 | 打开报告点名的页面，确认低置信或需要业务判断的内容 |
| 暂勿交付 | 先处理阻断问题，另存副本并复检 |

检查场景默认为会议室投屏。屏幕阅读或文档型 PPT 可改为 `--scenario screen` 或 `--scenario document`。

## 安全边界

- 只支持 `.pptx`，不声称支持旧 `.ppt` 格式。
- 默认只读；自动清理必须逐项授权，且永不覆盖源文件。
- 不自动删除隐藏页或外部链接，不自动重排版式，不重建整页图片。
- 不判断内容事实、审美好坏或业务结论。
- 完整报告可能包含页面预览、文字和文档属性，应与原 PPT 同级保护。

## GitHub Action

```yaml
- uses: kdnsna/pptlint@v1
  with:
    path: output.pptx
    scenario: present
    lang: zh-CN
    policy: pptlint-policy.yml
    artifact-name: pptlint-report
```

Action 会上传 HTML、JSON 和修复计划。固定生产环境也可以锁定完整版本标签，例如 `kdnsna/pptlint@v1.3.1`。

## 参与项目

- [提交问题](https://github.com/kdnsna/pptlint/issues)
- [提交已脱敏样本](https://github.com/kdnsna/pptlint/issues/new/choose)
- [从 DeckLint 迁移](docs/migration-from-decklint.md)
- [查看版本记录](CHANGELOG.md)

旧的 `decklint` 命令仍作为兼容别名存在，但不建议新项目继续使用；新用法统一采用 `pptlint`。

MIT License
