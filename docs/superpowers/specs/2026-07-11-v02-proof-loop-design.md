# DeckLint v0.2「质量闭环」设计规格

**状态：** 用户已确认

**发布目标：** DeckLint `0.2.0`、Git 标签 `v0.2.0`、浮动 Action 标签 `v0`

**联合案例：**《从生成到可交付：Ultimate PPT Master × DeckLint》

**语言与风格：** 严格、正式、中文优先

## 一、产品目标

DeckLint v0.2 将两次独立审计结果转换为一份可离线查看、可由机器验证的改进证明。DeckLint 继续坚持只读边界：DeckLint 负责诊断与比较，Ultimate PPT Master 负责理解 findings 并重做受影响页面。DeckLint 不修改 `.pptx`、不调用模型、不上传文件，也不以分数变化替代对主观审美的判断。

对外承诺集中为一句话：

> 生成演示文稿，审计交付风险，修复有证据的问题，并证明哪些质量真正得到改善。

核心命令为：

```bash
decklint compare before-report.json after-report.json \
  --output decklint-comparison \
  --fail-on-regression high
```

命令生成 `decklint-comparison.html` 与 `decklint-comparison.json`。比较通过时退出码为 `0`，触发回归门禁时为 `1`，报告无效或运行错误时为 `2`。

## 二、语言与表达合同

- 示例 PPT、案例网站、README 首屏、HTML 比较报告、发布说明和传播材料均以正式中文为主。
- README 提供清晰的英文入口，但不得让英文内容先于中文核心承诺出现。
- PPT 使用正式产品报告语气，不使用玩梗、夸张口号、聊天式碎片文案或未经证据支持的营销表述。
- HTML 人类可读界面采用简体中文；CLI 命令、参数、JSON 字段、Schema 标识、规则 ID 和代码注释继续使用英文，保持开发者接口稳定。
- “1+1＞2”作为项目目标，不作为反复出现的宣传口号；对外以“生成端与质量基础设施形成可验证闭环”进行正式表述。
- 中文排版必须避免孤行、标题意外换行、中英文间距混乱和过密段落。

## 三、范围与非目标

### 本次范围

- 确定性比较两个 `decklint-report/v1` JSON 报告。
- 发布 `decklint-comparison/v1` JSON Schema。
- 输出总分、五维分数、严重度和问题类别的前后变化。
- 将 findings 分类为已解决、持续存在和新增。
- 使用审计报告中已有的页面预览生成离线可视化比较报告。
- 为 CI 和 Agent 工作流提供回归门禁。
- 改善 `ai-generated` 档案对“原生标题文本但无 PowerPoint 标题占位符”页面的识别。
- 提供 Agent 修复闭环指南，直接消费现有审计 JSON，不复制规则逻辑。
- 完成真实 Ultimate PPT Master 前后对照案例、GitHub Pages、README 首屏改造、发布素材和 v0.2 Release。
- DeckLint v0.2 验证完成后，在 Ultimate PPT Master 中增加文档级、固定版本、可选的外部质量门禁入口。

### 明确不做

- 不提供自动修改 PPTX 的 `fix` 命令。
- 不在 DeckLint 内进行自然语言编辑。
- v0.2 不加入 `.decklint.yml`、品牌策略、SARIF 或 PR 评论。
- 不加入云存储、遥测、Desktop、Bridge、Provider 或模型调用。
- 不通过像素差异宣称页面审美得到改善。
- 不替换 Ultimate PPT Master 既有审计命令，不把 DeckLint 代码复制回旧仓。

## 四、比较命令合同

### CLI

```text
decklint compare BEFORE_REPORT AFTER_REPORT
  --output decklint-comparison
  --fail-on-regression none|low|medium|high|critical
```

默认值为 `--output decklint-comparison` 和 `--fail-on-regression high`。

比较命令只接受 JSON 报告。它必须验证 `schemaVersion == "decklint-report/v1"` 及所有必要字段，不重新打开源 PPTX。这样可以保证命令快速、可移植，并可直接消费 CI artifacts。

### 退出行为

- `0`：没有达到阈值的新增高置信 finding，且总分未下降。
- `1`：总分下降，或新增高置信 finding 达到配置阈值。
- `2`：报告不存在、JSON 损坏、Schema 不支持，或输出失败。

`--fail-on-regression none` 同时关闭新增问题严重度门禁和分数下降门禁，使比较命令只做观察与报告。

### Comparison Schema

`decklint-comparison/v1` 包含：

- 工具版本和比较 Schema 版本；
- 前后文件名、SHA-256、页数、profile、renderer 和源报告 Schema；
- 总分及五个维度的 before、after、delta；
- 各严重度数量的 before、after、delta；
- 门禁配置、通过状态和机器可读失败原因；
- `resolved[]`、`persistent[]`、`new[]`；
- 逐页前后预览与 findings 摘要；
- 可直接交给 Agent 的确定性中文摘要。

Schema 不包含绝对路径。相同输入多次运行必须生成字节级稳定的 JSON。

## 五、Finding 匹配规则

审计 finding ID 包含证据指纹，页面重做后可能变化。因此比较不能要求前后 ID 完全一致，而应使用确定性多重集合匹配：

1. 按 `(ruleId, slideIndex)` 分组。
2. 组内按归一化坐标、shape ID、evidence 和 finding ID 排序。
3. 按顺序配对到较小集合的数量。
4. 已配对项标记为 `persistent`，before 多出的项标记为 `resolved`，after 多出的项标记为 `new`。

比较项尽可能保留前后两个原始 finding。问题从一页移动到另一页时，在旧页视为已解决、在新页视为新增；这是更保守的 CI 解释。

## 六、AI 生成页面的标题语义

当前无障碍规则要求页面存在已填充的 PowerPoint 标题占位符。许多可编辑的 AI 生成页面使用普通原生文本框作为标题，可能形成系统性误报。

仅在 `ai-generated` profile 中，页面满足以下任一条件即可视为有标题：

- 存在已填充的 `title` 或 `ctrTitle` 占位符；
- 存在原生文本形状，位于页面顶部 25% 区域，显式最大字号至少 24 pt，文本长度为 1–160 个字符，且文本框宽度至少覆盖页面宽度的 20%。

模型和报告必须记录标题来源。Baseline profile 的既有行为保持不变。装饰文字、页脚、小字号文本和全页图片中的栅格化文字不构成语义标题。

这是确定性的语义回退，不是审美判断。

## 七、架构和文件边界

- `src/decklint/comparison.py`：报告校验、确定性匹配、分数变化和门禁结果。
- `src/decklint/comparison_report.py`：比较 JSON 组装及单文件 HTML 渲染。
- `src/decklint/cli.py`：新增 `compare` 子命令并映射退出码。
- `src/decklint/model.py`：提供语义标题推断所需的标准化文本几何信息。
- `src/decklint/rules.py`：实现 profile 专属标题判断。
- `src/decklint/report.py`：在每页报告中发布 `titleSource`。
- `schema/decklint-report-v1.schema.json`：以可选字段方式允许新增 `titleSource`，不改变 v1 标识；0.1 报告继续通过校验。
- `schema/decklint-comparison-v1.schema.json`：公开比较合同。
- `tests/test_comparison.py`：匹配、分数变化、门禁、损坏输入和确定性测试。
- `tests/test_ai_generated_titles.py`：阳性、阴性、边界及 baseline 不变测试。
- `tests/test_comparison_report.py`：离线 HTML、路径脱敏、预览配对和 Schema 校验。

比较模块不得读取 ZIP/XML，也不得调用 renderer；它只消费已经验证的审计报告字典。

## 八、错误与安全处理

- 解析前拒绝超过 100 MiB 的报告。
- 使用标准库解析 JSON，并拒绝非 object 根节点。
- Schema 版本不支持时返回明确的运行错误。
- HTML 中所有来自报告的字符串必须转义。
- 不嵌入远程 CSS、JavaScript、图片、统计代码或字体。
- 缺失预览仅标记为证据不足，不视为 PPT 质量回归。
- 不访问 finding evidence 中的任何 URL。
- JSON 和 HTML 不泄露输入报告的绝对路径。
- 两份报告完成验证且比较组装成功后才写输出文件。

## 九、Ultimate PPT Master 联合案例

### 叙事结构

创建一份 9 页、16:9、可编辑的正式中文 PowerPoint，标题为《从生成到可交付》，副标题为“AI 演示文稿质量闭环”。目标受众为 AI 开发者、演示文稿创作者和 GitHub 用户。

1. AI 已经可以生成页面，但交付质量仍需证据。
2. Ultimate PPT Master 生成可编辑初稿。
3. DeckLint 在本地审计结构质量。
4. Findings 转化为边界清晰的逐页修复清单。
5. Ultimate PPT Master 只重做受影响页面。
6. DeckLint 再次审计并比较。
7. 最终 PPT 仍然可编辑且不离开本地。
8. 两个工具保持清晰分工。
9. 以可复现命令结束，而非泛化宣传口号。

### 生成纪律

- 使用已安装的 `ultimate-ppt-master` Skill，选择可编辑 PPTX 模式。
- 内容来源只使用 DeckLint 与 Ultimate PPT Master 的公开仓库资料。
- 严格执行 Strategist、Eight Confirmations、Executor、逐页 SVG、质量检查、讲稿、finalize 和 export 门禁。
- 保留第一份合法结构初稿为 `before.pptx`；不得为了降低分数而人为损坏或蓄意制造错误。
- 使用 v0.2 `ai-generated` profile 审计 `before.pptx`。
- 将真实高置信 findings 转换为逐页修复台账。
- 只重做受影响页面，并导出独立的 `after.pptx`。
- 再次审计并生成比较报告。

若初稿没有可修复的高置信 finding，可以依据真实低置信 warning 和人工视觉 QA 进行优化，但不得把提示性改动包装为分数证明。公开案例必须区分“规则证据支持的修复”和“人工视觉润色”。

### 案例验收

- `after.pptx` 不得出现新的 high/critical finding。
- 总分提高，且任何评分维度不得下降。
- 至少一个真实 finding 被标记为已解决；若没有，则必须将案例表述为“清洁生成验证”，不得称为修复成功。
- 每项公开修复对应 finding ID，或明确标为独立视觉 QA 项。
- 两份 PPTX 均能打开并渲染相同页数，且保留原生可编辑文字和形状。
- 修复所有非预期重叠、裁切和换行问题。

## 十、公开证明与仓库装修

DeckLint 仓库新增：

- `examples/ultimate-ppt-master-proof/before.pptx`；
- `examples/ultimate-ppt-master-proof/after.pptx`；
- 前后两份审计 JSON/HTML；
- 比较 JSON/HTML；
- 正式中文案例说明和修复台账；
- `site/index.html` 中文优先单页案例站，不使用追踪代码；
- `.github/workflows/pages.yml` Pages 部署工作流；
- 使用真实分数变化和已解决问题更新 README 首屏；
- 10 秒前后对照 GIF；
- 1200×630 `assets/social-preview.png`；
- `docs/launch-kit.md` 中文主文及简短英文发布摘要。

Pages 上线后，将仓库 homepage URL 指向已验证的 Pages 地址。Topics 包含 `powerpoint`、`pptx`、`linter`、`presentation`、`accessibility`、`ai-agents` 和 `github-actions`。Release 附带 wheel、sdist、两份 PPTX 和比较 HTML。

在 PyPI 真正发布前，README 不得宣称 `uvx decklint` 已可直接使用。授权前以 Release wheel 的可执行命令为主；Trusted Publishing 成功后切换为 `uvx decklint`，并在全新环境中验证。

## 十一、跨仓边界

只有在 DeckLint `v0.2.0` 和公开资产全部验证后，Ultimate PPT Master 才增加文档级集成：

- 链接 DeckLint 联合案例；
- 提供固定版本的 `uvx decklint==0.2.0 audit` 与 `compare` 可选流程；
- 明确 DeckLint 是外部 MIT 质量门禁；
- 保留旧审计命令，不增加 DeckLint 强制运行时依赖。

不复制 DeckLint 源码，不把 Ultimate PPT Master 的生成器、模板、Provider、Desktop 或 Bridge 代码迁入 DeckLint。

## 十二、测试与发布门禁

### 自动化门禁

- Python 3.10–3.13，macOS、Windows、Linux 全矩阵。
- v0.1 审计与 Schema 行为保持向后兼容。
- 每个比较分类器具备阳性、阴性、边界、重复项和损坏报告测试。
- `decklint-comparison/v1` 同时校验动态报告与仓库内公开案例。
- 相同输入多次比较生成字节级一致的 JSON 和 HTML。
- 比较 HTML 完全离线，不含网络请求和绝对路径。
- 回归门禁覆盖分数下降、各阈值新增问题、`none` 和退出码 `2`。
- AI 标题推断覆盖占位符、语义标题、页脚拒绝、小字号拒绝、栅格化拒绝及 baseline 不变。
- GitHub Pages、Action `v0.2` 标签、wheel/sdist、全新安装、`python -m decklint`、console script 和 `uvx` 全部验证。
- 依赖漏洞与许可证检查通过。

### 人工与视觉门禁

- 全尺寸逐页检查 before 和 after PPT。
- 在桌面及窄屏视口检查比较 HTML 与案例站。
- 验证 Pages 链接、Release assets、README、仓库 metadata 和双仓互链。
- 确认仓库不包含私有源材料、绝对本地路径、密钥、批注或个人元数据。
- 中文标题、正文、标点、中英文间距及字体回退均通过人工检查。

## 十三、发布顺序

1. 在隔离分支实现 compare 与标题语义，并完成验证。
2. 使用 Ultimate PPT Master 生成合法 before deck。
3. 审计、修复、局部重做、复审并生成证明资产。
4. 完成 Pages、README、发布材料和中文案例。
5. 本地门禁与代码复审通过后合并 `main`。
6. 等待 `main` 全部 CI 通过。
7. 发布 `v0.2.0`、更新 `v0`、附加验证资产，并等待 tag CI。
8. 启用并验证 GitHub Pages，更新仓库 homepage。
9. 完成 PyPI Trusted Publisher 授权并发布 `0.2.0`，在全新环境验证 `uvx decklint`。
10. 在 Ultimate PPT Master 增加固定版本的可选文档入口，并验证其自身 CI。

## 十四、完成定义

发布完成时，访客必须能够：

1. 从 README 中文首屏理解产品；
2. 按文档成功安装或运行准确版本；
3. 离线审计 PPTX 并比较前后报告；
4. 查看真实 Ultimate PPT Master 修复案例及可追踪证据；
5. 在 CI 中使用 `kdnsna/decklint@v0`；
6. 打开 Pages 案例站和 v0.2 Release assets；
7. 从 Ultimate PPT Master 的可选入口进入质量闭环，且两个仓库仍保持解耦。
