from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "site" / "lab"
DATA = LAB / "cases.json"
VALIDATION = ROOT / "validation" / "public-sample-validation.json"
sys.path.insert(0, str(ROOT / "src"))

from decklint.repair_catalog import recipe_for  # noqa: E402


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


VISUAL_LABELS = {
    "small-text": "小字号",
    "clipping": "末行截断",
    "overlap": "重叠",
    "font": "字体缺失",
    "contrast": "低对比",
    "flattened": "整页图片",
    "notes": "备注泄露",
    "hidden": "隐藏页",
    "link": "本地外链",
    "broken": "关系断裂",
    "size": "重复媒体",
    "brand": "规范越界",
}

# 每类风险在「修改前」幻灯片上显示的标题
SLIDE_TITLE = {
    "small-text": "季度经营情况回顾与下阶段重点",
    "clipping": "项目阶段性成果与后续计划",
    "overlap": "产品能力矩阵与竞品对比",
    "font": "品牌升级发布会主题演讲",
    "contrast": "企业视觉规范（浅灰版）",
    "flattened": "年度战略发布会完整版",
    "notes": "内部研讨：报价策略与结论",
    "hidden": "备用报价页与编辑者信息",
    "link": "季度营收图表（引用本地文件）",
    "broken": "自动生成的汇报材料",
    "size": "产品发布会物料包",
    "brand": "区域市场活动方案",
}

# 每类风险「修改后」的标题/副标题
AFTER = {
    "small-text": ("结论先行，一眼看懂", "现场可读 · 层次清晰"),
    "clipping": ("末行完整显示", "留足高度 · 换机复测"),
    "overlap": ("标题和说明各就各位", "安全间距 · 现场可读"),
    "font": ("换台电脑，照样还原", "批准字体 · 复测换行"),
    "contrast": ("投影开灯仍然清楚", "对比达标 · 品牌不变"),
    "flattened": ("想改就改，对象都在", "原生对象 · 可编辑"),
    "notes": ("交付副本已清理备注", "明确授权 · 原稿不动"),
    "hidden": ("只保留确认可外发内容", "隐藏页人工判断 · 元数据可清理"),
    "link": ("离开原电脑也能打开", "外链人工判断 · 断网复测"),
    "broken": ("结构完整，打开无忧", "关系重建 · 无修复提示"),
    "size": ("体积小了，照样清晰", "媒体去重 · 18 MB"),
    "brand": ("按规范走，一次过审", "字体色板 · 全部批准"),
}

MODE_LABELS = {
    "cleanup-copy": "用户授权后，PPTLint 清理独立副本",
    "guided-powerpoint": "在 PowerPoint 中按步骤处理",
    "agent-rebuild": "交给人或 Agent 重建、重排",
    "human-decision": "先由人判断，不建议自动处理",
}
EXECUTOR_LABELS = {
    "pptlint": "PPTLint",
    "powerpoint": "PowerPoint",
    "generic-agent": "通用 Agent",
    "ultimate-ppt-master": "Ultimate PPT Master",
    "powerpoint-copilot": "PowerPoint Copilot",
}

FILTERS = [
    ("all", "全部"),
    ("readability", "现场可读性"),
    ("stability", "换电脑稳定性"),
    ("editable", "可编辑交接"),
    ("privacy", "隐私与外发"),
    ("integrity", "文件完整性"),
    ("size", "文件体积"),
    ("policy", "团队规范"),
]
CAT_SLUG = {label: slug for slug, label in FILTERS if slug != "all"}


def hairlines(n):
    return "\n              ".join("<i></i>" for _ in range(n))


def before_art(visual):
    if visual == "small-text":
        return f"""<div class="scene scene-st">
              <div class="scene-st__cols">
                <div class="scene-st__col">{hairlines(8)}</div>
                <div class="scene-st__col">{hairlines(8)}</div>
                <div class="scene-st__col">{hairlines(8)}</div>
              </div>
              <span class="scene__tag scene-st__zoom">12 pt · 268 字</span>
            </div>"""
    if visual == "clipping":
        return """<div class="scene scene-cl">
              <div class="scene-cl__box">
                <i></i><i></i><i></i><i></i><i></i>
              </div>
              <div class="scene-cl__cut"></div>
              <span class="scene-cl__x">末行截断 ✂</span>
            </div>"""
    if visual == "overlap":
        return """<div class="scene scene-ov">
              <div class="scene-ov__a">标题：产品能力矩阵</div>
              <div class="scene-ov__b">说明：与竞品对比分析</div>
              <div class="scene-ov__hit"></div>
            </div>"""
    if visual == "font":
        return """<div class="scene scene-ft">
              <div class="scene-ft__row">
                <span class="scene-ft__bad">字体：演示专用体</span>
                <span class="scene-ft__arrow">→</span>
                <span class="scene-ft__bad scene-ft__bad--red">宋体（替换）</span>
              </div>
              <div class="scene__ttl scene-ft__reflow">标题被替换后多出一行，整体下移</div>
            </div>"""
    if visual == "contrast":
        return """<div class="scene scene-ct">
              <div class="scene-ct__ln"></div>
              <div class="scene-ct__ln" style="width:82%"></div>
              <div class="scene-ct__ln" style="width:64%"></div>
              <div class="scene-ct__dim"></div>
              <span class="scene-ct__lamp">开灯后 ≈ 消失</span>
            </div>"""
    if visual == "flattened":
        return """<div class="scene scene-fl">
              <span class="scene-fl__lock">🖼 整页图片 99% · 不可选中</span>
            </div>"""
    if visual == "notes":
        return """<div class="scene scene-nt">
              <div class="scene-nt__slide"><span></span></div>
              <div class="scene-nt__notes">备注：报价底线 ¥__ · 未公开结论…</div>
            </div>"""
    if visual == "hidden":
        return """<div class="scene scene-hd">
              <div class="scene-hd__strip">
                <div class="scene-hd__th"></div>
                <div class="scene-hd__th off"></div>
                <div class="scene-hd__th"></div>
                <div class="scene-hd__th off"></div>
              </div>
              <div class="scene-hd__meta">作者 <b>Li Wei</b><br>2 张隐藏页</div>
            </div>"""
    if visual == "link":
        return """<div class="scene scene-lk">
              <div class="scene-lk__chart"><i style="height:40%"></i><i style="height:72%"></i><i style="height:55%"></i><i style="height:92%"></i></div>
              <div class="scene-lk__path">↳ 桌面/报告.xlsx <span class="x">找不到源文件</span></div>
            </div>"""
    if visual == "broken":
        return """<div class="scene scene-bk">
              <div class="scene-bk__crack"></div>
              <span class="scene-bk__warn">⚠ 包关系断裂 · 需修复</span>
            </div>"""
    if visual == "size":
        grid = "\n              ".join("<i></i>" for _ in range(14))
        return f"""<div class="scene scene-sz">
              <div class="scene-sz__grid">
                {grid}
              </div>
              <div class="scene-sz__bar"><i></i></div>
              <span class="scene__cap">86 MB · 14 份重复媒体</span>
            </div>"""
    if visual == "brand":
        return """<div class="scene scene-br">
              <div class="scene-br__fonts">
                <span>思源黑体</span><span class="no">艺术体</span><span>苹方</span><span class="no">手写体</span>
              </div>
              <div class="scene-br__sw">
                <i style="background:#E85D2C"></i><i class="no" style="background:#a855f7"></i>
                <i style="background:#0A1628"></i><i class="no" style="background:#22d3ee"></i>
                <i style="background:#10B981"></i><i class="no" style="background:#f43f5e"></i>
                <i style="background:#f59e0b"></i>
              </div>
              <span class="scene__cap">4 非批准字体 · 7 越界色</span>
            </div>"""
    return """<div class="scene"><div class="scene__ttl">交付风险</div></div>"""


def before_slide(visual, chip, sb):
    title = SLIDE_TITLE.get(visual, "交付前的一页")
    return f"""<figure class="pslide pslide--before">
              <div class="pslide__chrome"><span></span><span></span><span></span><em>修改前.pptx</em></div>
              <div class="pslide__body">
                <div class="pslide__eyebrow-bad">交付风险 · 未处理</div>
                <div class="pslide__title-bad">{title}</div>
                {before_art(visual)}
              </div>
              <span class="pslide__flag pslide__flag--bad">{chip}</span>
              <span class="score-badge score-badge--bad">{sb}<small>修改前</small></span>
            </figure>"""


def after_slide(visual, sa):
    headline, sub = AFTER.get(visual, ("已按报告处理", "可编辑 · 现场可读"))
    return f"""<figure class="pslide pslide--after">
              <div class="pslide__chrome"><span></span><span></span><span></span><em>交付版.pptx</em></div>
              <div class="pslide__body">
                <div class="pslide__brandbar"></div>
                <div class="pslide__kicker">已按报告处理</div>
                <div class="pslide__headline">{headline}</div>
                <div class="pslide__sub">{sub}</div>
                <div class="pslide__cleanchart"><i style="height:46%"></i><i style="height:62%"></i><i style="height:74%"></i><i style="height:100%"></i></div>
              </div>
              <span class="pslide__flag pslide__flag--good">复检通过</span>
              <span class="score-badge score-badge--good">{sa}<small>修改后</small></span>
            </figure>"""


def render_case(case: dict) -> str:
    slug = case["slug"]
    cat = case["category"]
    visual = case.get("visual", "")
    chip = VISUAL_LABELS.get(visual, "风险")
    recipe = recipe_for(case["rule"])
    mode = MODE_LABELS[recipe.mode]
    executors = "、".join(EXECUTOR_LABELS[item] for item in recipe.executors)
    boundary = case.get(
        "boundary",
        "PPTLint 负责发现和复检；只有明确标为可清理的内容，才会在授权后写入独立副本。",
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{esc(case['title'])}：{esc(case['scene'])}">
  <link rel="canonical" href="https://kdnsna.github.io/pptlint/lab/cases/{esc(slug)}.html">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{esc(case['title'])} · PPTLint 案例">
  <meta property="og:description" content="{esc(case['scene'])}">
  <meta property="og:url" content="https://kdnsna.github.io/pptlint/lab/cases/{esc(slug)}.html">
  <meta property="og:image" content="https://kdnsna.github.io/pptlint/assets/pptlint-before-after-hero.png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(case['title'])} · PPTLint 案例">
  <meta name="twitter:description" content="{esc(case['scene'])}">
  <meta name="twitter:image" content="https://kdnsna.github.io/pptlint/assets/pptlint-before-after-hero.png">
  <title>{esc(case['title'])} · PPTLint 案例</title>
  <link rel="icon" href="../../favicon.svg">
  <link rel="stylesheet" href="../../shared.css">
</head>
<body>
  <nav class="nav">
    <div class="container nav__inner">
      <a class="nav__logo" href="../../">PPTLINT</a>
      <div class="nav__links">
        <a class="nav__link" href="../../">首页</a>
        <a class="nav__link" href="../" aria-current="page">案例</a>
        <a class="nav__link" href="../../proof-loop/comparison.html">Proof Loop</a>
        <a class="nav__link" href="https://github.com/kdnsna/pptlint">GitHub</a>
      </div>
    </div>
  </nav>

  <main><header class="case-hero">
    <div class="container">
      <span class="case-hero__kicker reveal">{esc(cat)} · 可控演示</span>
      <h1 class="case-hero__title reveal">{esc(case['title'])}</h1>
      <p class="case-hero__lead reveal">{esc(case['scene'])}</p>
    </div>
  </header>

  <section class="section section--white">
    <div class="container">
      <div class="showcase reveal reveal--scale" style="margin-top:0;">
        <div class="showcase__stage">
          <span class="showcase__eyebrow">同一页幻灯片 · 处理前后对比</span>
          <div class="deck">
            {before_slide(visual, chip, case['scoreBefore'])}
            <div class="deck__arrow">
              <span class="deck__arrow-chip">检查 → 按计划修改 → 复检</span>
              <span class="deck__arrow-line">→</span>
            </div>
            {after_slide(visual, case['scoreAfter'])}
          </div>
          <p class="showcase__caption">分数从 <b>{esc(case['scoreBefore'])}</b> 到 <b>{esc(case['scoreAfter'])}</b>，只代表该规则通过，不代表审美评价。</p>
        </div>
      </div>
      <div class="case-finding reveal">
        <div class="case-finding__item"><strong>PPTLint 发现</strong>{esc(case['before'])}</div>
        <div class="case-finding__item"><strong>处理结果</strong>{esc(case['after'])}</div>
      </div>
    </div>
  </section>

  <section class="section section--muted">
    <div class="container">
      <h2 class="section__title reveal">从发现到复检</h2>
      <p class="section__desc reveal">这是用来解释单一风险的可控演示，并非客户证言；分数只反映规则检查的结果。</p>
      <div class="steps">
        <div class="step reveal">
          <div class="step__num">01 · PPTLint 发现</div>
          <h3 class="step__title">这一页发现了什么</h3>
          <p class="step__body">{esc(case['before'])}</p>
        </div>
        <div class="step reveal">
          <div class="step__num">02 · 选择处理方式</div>
          <h3 class="step__title">{esc(mode)}</h3>
          <p class="step__body">推荐：{esc(executors)}。{esc(case['after'])}</p>
        </div>
        <div class="step reveal">
          <div class="step__num">03 · 同场景复检</div>
          <h3 class="step__title">验收方式</h3>
          <p class="step__body">原问题消失，不新增高置信问题，原文件保持不变。<br><code>pptlint check deck.pptx --scenario present --lang zh-CN</code></p>
        </div>
      </div>
      <div class="disclosure reveal" style="margin-top:24px;">
        规则：<code>{esc(case['rule'])}</code> · 处理方式：<code>{esc(recipe.mode)}</code>。{esc(boundary)} 本页是可控演示，不是客户证言；PPTLint 也不会把审美偏好当成错误。
      </div>
    </div>
  </section>

  <section class="section section--white">
    <div class="container">
      <div class="case-cta reveal reveal--scale">
        <div>
          <h2 class="case-cta__title">再看看另外 11 个交付案例</h2>
          <p class="case-cta__sub">从投屏翻车，到隐私外发和可编辑交接。</p>
        </div>
        <div class="case-cta__actions">
          <a class="btn btn--primary" href="../index.html">返回案例实验室</a>
          <a class="btn btn--secondary" href="https://github.com/kdnsna/pptlint">GitHub</a>
        </div>
      </div>
    </div>
  </section></main>

  <footer class="footer">
    <div class="container">
      <div class="footer__brand">PPTLINT</div>
      <p class="footer__tagline">本地 · 只读 · 不上传 · 不调用模型的 PowerPoint 交付前检查。</p>
      <div class="footer__links">
        <a class="footer__link" href="../../">产品首页</a>
        <a class="footer__link" href="../">案例实验室</a>
        <a class="footer__link" href="../../proof-loop/comparison.html">真实 Proof Loop</a>
        <a class="footer__link" href="https://github.com/kdnsna/pptlint">GitHub</a>
      </div>
      <p class="footer__copy">PPTLint · Local, read-only PowerPoint preflight</p>
    </div>
  </footer>

  <script src="../../shared.js"></script>
</body>
</html>
"""


def render_card(case: dict) -> str:
    slug = CAT_SLUG.get(case["category"], "all")
    return f'''        <article class="card reveal" data-category="{slug}">
          <span class="card__tag">{esc(case['category'])}</span>
          <h3 class="card__title">{esc(case['title'])}</h3>
          <p class="card__body">{esc(case['scene'])}</p>
          <div class="case-compare">
            <div class="case-compare__state case-compare__state--before"><span class="case-compare__score">{esc(case['scoreBefore'])}</span><span class="case-compare__label">修改前</span></div>
            <div class="case-compare__state case-compare__state--after"><span class="case-compare__score">{esc(case['scoreAfter'])}</span><span class="case-compare__label">修改后</span></div>
          </div>
          <p class="case-card__meta">发现：{esc(case['before'])}<br>处理：{esc(case['after'])}</p>
          <a class="card__link" href="cases/{esc(case['slug'])}.html">查看检查依据 →</a>
        </article>'''


INDEX_TMPL = '''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="12 个一眼看懂的 PowerPoint 交付风险前后对比，以及热门 AI PPT 项目的公开样本实测。">
  <link rel="canonical" href="https://kdnsna.github.io/pptlint/lab/">
  <meta property="og:type" content="website">
  <meta property="og:title" content="PPTLint 交付案例实验室">
  <meta property="og:description" content="12 个交付风险前后对比，以及 33 份公开 PPTX 的固定来源验证。">
  <meta property="og:url" content="https://kdnsna.github.io/pptlint/lab/">
  <meta property="og:image" content="https://kdnsna.github.io/pptlint/assets/pptlint-before-after-hero.png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="PPTLint 交付案例实验室">
  <meta name="twitter:description" content="12 个交付风险前后对比，以及 33 份公开 PPTX 的固定来源验证。">
  <meta name="twitter:image" content="https://kdnsna.github.io/pptlint/assets/pptlint-before-after-hero.png">
  <title>PPTLint 交付案例实验室</title>
  <link rel="icon" href="../favicon.svg">
  <link rel="stylesheet" href="../shared.css">
</head>
<body>
  <nav class="nav">
    <div class="container nav__inner">
      <a class="nav__logo" href="../">PPTLINT</a>
      <div class="nav__links">
        <a class="nav__link" href="../">首页</a>
        <a class="nav__link" href="./" aria-current="page">案例</a>
        <a class="nav__link" href="../proof-loop/comparison.html">Proof Loop</a>
        <a class="nav__link" href="https://github.com/kdnsna/pptlint">GitHub</a>
      </div>
    </div>
  </nav>

  <main><header class="hero">
    <div class="container">
      <div class="lab-hero">
        <div>
          <p class="hero__eyebrow reveal">PPTLint 交付案例实验室</p>
          <h1 class="hero__title reveal">好看的 PPT，<br>未必就能直接发出去。</h1>
          <p class="hero__subtitle reveal">这里不评审美。PPTLint 先发现问题、生成修复任务；你明确授权时，它能清理独立副本里的备注、批注和作者信息，复杂版式仍交给人或 Agent。</p>
        </div>
        <div class="lab-hero__stat reveal reveal--scale">
          <div class="lab-hero__stat-big"><span data-count="33">33</span> / <span data-count="383">383</span></div>
          <p style="color: rgba(255,255,255,0.72); margin: 0 0 14px; position: relative;">33 份固定来源 PPTX · 383 页 · 4 个项目族 · 0 失败</p>
          <div class="lab-hero__tags">
            <span>本地</span><span>只读</span><span>不上传</span><span>不调用模型</span>
          </div>
        </div>
      </div>
    </div>
  </header>

  <section class="section section--muted">
    <div class="container">
      <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 12px; margin-bottom: 20px;">
        <h2 class="section__title reveal" style="margin-bottom: 0;">前后对比</h2>
        <p class="text-muted">每个案例都公开检查规则、处理边界和复检方式。</p>
      </div>

      <div class="filters reveal" aria-label="案例筛选">
        {filters}
      </div>
      <p id="filter-status" class="filter-status" aria-live="polite">当前显示 12 个案例</p>

      <div class="card-grid card-grid--3" id="case-grid">
{cards}
      </div>

      <p class="note" style="text-align: center; margin-top: 40px; border: none; padding: 0;">100 分只代表这些规则通过，不代表审美满分或绝对零风险。</p>
    </div>
  </section>

  <section class="section section--white">
    <div class="container">
      <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 12px; margin-bottom: 20px;">
        <h2 class="section__title reveal" style="margin-bottom: 0;">33 份公开样本验证</h2>
        <p class="text-muted">383 页 · 4 个项目族 · 0 运行失败 · 修复计划覆盖率 100%。以下是 4 个精选样本。</p>
      </div>
      <div class="table-wrap reveal reveal--scale">
        <table class="table">
          <thead>
            <tr><th>项目</th><th>结果</th><th>分数</th><th>发现项</th><th>备注</th></tr>
          </thead>
          <tbody>
{market_rows}
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <section class="section section--muted">
    <div class="container">
      <div class="case-cta reveal reveal--scale">
        <div>
          <h2 class="case-cta__title">真实九页 PPT：83 → 100</h2>
          <p class="case-cta__sub">103 项高置信问题已处理；21 项低置信提醒持续存在，新增 3 项低置信提示，新增高置信问题为 0。</p>
        </div>
        <div class="case-cta__actions">
          <a class="btn btn--primary" href="../proof-loop/comparison.html">查看完整证据</a>
        </div>
      </div>
    </div>
  </section></main>

  <footer class="footer">
    <div class="container">
      <div class="footer__brand">PPTLINT</div>
      <p class="footer__tagline">PowerPoint 的本地、只读、确定性质量基础设施。</p>
      <div class="footer__links">
        <a class="footer__link" href="../">产品首页</a>
        <a class="footer__link" href="../proof-loop/comparison.html">Proof Loop</a>
        <a class="footer__link" href="https://github.com/kdnsna/pptlint">GitHub</a>
      </div>
      <p class="footer__copy">MIT · Deterministic · Local · Read-only</p>
    </div>
  </footer>

  <script src="../shared.js"></script>
'''

FILTER_JS = '''  <script>
    document.querySelectorAll('.filter').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter').forEach(b => {
          b.classList.remove('active');
          b.setAttribute('aria-pressed', 'false');
        });
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
        const cat = btn.dataset.category;
        let count = 0;
        document.querySelectorAll('#case-grid .card').forEach(card => {
          const show = (cat === 'all' || card.dataset.category === cat);
          card.style.display = show ? '' : 'none';
          if (show) { card.classList.add('in'); count += 1; }
        });
        document.querySelector('#filter-status').textContent = `当前显示 ${count} 个案例`;
      });
    });
  </script>
</body>
</html>
'''


def render_index(data: dict) -> str:
    cases = data["cases"]
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    results = {item["sha256"]: item for item in validation["results"]}
    audits = []
    for featured in data["featuredSamples"]:
        current = results[featured["sha256"]]
        audits.append({**featured, **current})
    filters = "\n        ".join(
        f'<button type="button" class="filter{" active" if slug == "all" else ""}" aria-pressed="{"true" if slug == "all" else "false"}" data-category="{slug}">{esc(label)}</button>'
        for slug, label in FILTERS
    )
    cards = "\n".join(render_card(c) for c in cases)
    market_rows = "\n".join(
        f'''            <tr>
              <td><a class="card__link" href="{esc(a['url'])}" target="_blank" rel="noopener">{esc(a['label'])}</a></td>
              <td><span class="badge badge--warn">需复核</span></td>
              <td class="mono">{esc(a['score'])}</td>
              <td class="mono">{esc(a['findingCount'])}</td>
              <td class="text-muted">{esc(a['note'])}</td>
            </tr>'''
        for a in audits
    )
    return (
        INDEX_TMPL.replace("{filters}", filters)
        .replace("{cards}", cards)
        .replace("{market_rows}", market_rows)
        + FILTER_JS
    )


def outputs() -> dict[Path, str]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if len(cases) != 12:
        raise ValueError("The case lab must contain exactly 12 completed cases")
    built = {LAB / "index.html": render_index(data)}
    for case in cases:
        built[LAB / "cases" / f'{case["slug"]}.html'] = render_case(case)
    return built


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    failures: list[str] = []
    for path, content in outputs().items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                failures.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    if failures:
        raise SystemExit("Case lab is stale: " + ", ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
