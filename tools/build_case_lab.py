from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "site" / "lab"
DATA = LAB / "cases.json"


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
    "现场可读性":   ("结论先行，一眼看懂", "现场可读 · 层次清晰"),
    "换电脑稳定性": ("换台电脑，照样还原", "字体合规 · 链接内嵌"),
    "可编辑交接":   ("想改就改，对象都在", "原生对象 · 可编辑"),
    "隐私与外发":   ("外发之前，清理干净", "备注清理 · 隐藏页移除"),
    "文件完整性":   ("结构完整，打开无忧", "关系重建 · 无修复提示"),
    "文件体积":     ("体积小了，照样清晰", "去重 · 18 MB"),
    "团队规范":     ("按规范走，一次过审", "字体色板 · 全部批准"),
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


def after_slide(cat, sa):
    headline, sub = AFTER.get(cat, ("已按报告处理", "可编辑 · 现场可读"))
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
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{esc(case['title'])}：{esc(case['scene'])}">
  <link rel="canonical" href="https://kdnsna.github.io/pptlint/lab/cases/{esc(slug)}.html">
  <title>{esc(case['title'])} · PPTLint 案例</title>
  <link rel="icon" href="../../favicon.svg">
  <link rel="stylesheet" href="../../shared.css">
</head>
<body>
  <nav class="nav">
    <div class="container nav__inner">
      <a class="nav__logo" href="../../">PPTLINT</a>
      <div class="nav__links">
        <a class="nav__link" href="../../">产品首页</a>
        <a class="nav__link" href="../">案例实验室</a>
        <a class="nav__link" href="../../proof-loop/comparison.html">Proof Loop</a>
        <a class="nav__link" href="https://github.com/kdnsna/pptlint">GitHub</a>
      </div>
    </div>
  </nav>

  <header class="case-hero">
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
              <span class="deck__arrow-chip">PPTLint 检查 + 人工处理</span>
              <span class="deck__arrow-line">→</span>
            </div>
            {after_slide(cat, case['scoreAfter'])}
          </div>
          <p class="showcase__caption">分数从 <b>{esc(case['scoreBefore'])}</b> 到 <b>{esc(case['scoreAfter'])}</b>，只代表该规则通过，不代表审美评价。</p>
        </div>
      </div>
      <div class="case-finding reveal">
        <div class="case-finding__item"><strong>PPTLint 发现</strong>{esc(case['before'])}</div>
        <div class="case-finding__item"><strong>人工处理</strong>{esc(case['after'])}</div>
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
          <div class="step__num">02 · 人工处理</div>
          <h3 class="step__title">处理后复检</h3>
          <p class="step__body">{esc(case['after'])}</p>
        </div>
        <div class="step reveal">
          <div class="step__num">03 · 同场景复检</div>
          <h3 class="step__title">复检命令</h3>
          <p class="step__body"><code>pptlint check deck.pptx --scenario present --lang zh-CN</code></p>
        </div>
      </div>
      <div class="disclosure reveal" style="margin-top:24px;">
        规则：<code>{esc(case['rule'])}</code>。PPTLint 不会替你改文件，也不会把审美偏好当成错误来报。本页是一个可控演示，用来说明这条规则在真实交付里是怎么检查、边界在哪里。
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
  </section>

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
  <title>PPTLint 交付案例实验室</title>
  <link rel="icon" href="../favicon.svg">
  <link rel="stylesheet" href="../shared.css">
</head>
<body>
  <nav class="nav">
    <div class="container nav__inner">
      <a class="nav__logo" href="../">PPTLINT</a>
      <div class="nav__links">
        <a class="nav__link" href="../">产品首页</a>
        <a class="nav__link" href="../proof-loop/comparison.html">Proof Loop</a>
        <a class="nav__link" href="https://github.com/kdnsna/pptlint">GitHub</a>
      </div>
    </div>
  </nav>

  <header class="hero">
    <div class="container">
      <div class="lab-hero">
        <div>
          <p class="hero__eyebrow reveal">PPTLint 交付案例实验室</p>
          <h1 class="hero__title reveal">好看的 PPT，<br>未必就能直接发出去。</h1>
          <p class="hero__subtitle reveal">这里不评审美，也不替你改文件。我们把会议室、换电脑、可编辑交接和隐私外发里真会翻车的地方，拆成 12 个一眼就能看懂的前后对比。</p>
        </div>
        <div class="lab-hero__stat reveal reveal--scale">
          <div class="lab-hero__stat-big"><span data-count="12">12</span> + <span data-count="4">4</span></div>
          <p style="color: rgba(255,255,255,0.72); margin: 0 0 14px; position: relative;">12 个可控前后演示 · 4 个热门开源项目样本实测</p>
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

      <div class="filters reveal">
        {filters}
      </div>

      <div class="card-grid card-grid--3" id="case-grid">
{cards}
      </div>

      <p class="note" style="text-align: center; margin-top: 40px; border: none; padding: 0;">100 分只代表这些规则通过，不代表审美满分或绝对零风险。</p>
    </div>
  </section>

  <section class="section section--white">
    <div class="container">
      <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 12px; margin-bottom: 20px;">
        <h2 class="section__title reveal" style="margin-bottom: 0;">开源项目样本实测</h2>
        <p class="text-muted">公开 AI PPT 项目的样本，仅做演示性检查，不代表对该项目的评价。</p>
      </div>
      <div class="table-wrap reveal reveal--scale">
        <table class="table">
          <thead>
            <tr><th>项目</th><th>结果</th><th>分数</th><th>发现组</th><th>备注</th></tr>
          </thead>
          <tbody>
{market_rows}
          </tbody>
        </table>
      </div>
    </div>
  </section>

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
        document.querySelectorAll('.filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const cat = btn.dataset.category;
        document.querySelectorAll('#case-grid .card').forEach(card => {
          const show = (cat === 'all' || card.dataset.category === cat);
          card.style.display = show ? '' : 'none';
          if (show) card.classList.add('in');
        });
      });
    });
  </script>
</body>
</html>
'''


def render_index(data: dict) -> str:
    cases = data["cases"]
    audits = data["marketAudits"]
    filters = "\n        ".join(
        f'<button class="filter{" active" if slug == "all" else ""}" data-category="{slug}">{esc(label)}</button>'
        for slug, label in FILTERS
    )
    cards = "\n".join(render_card(c) for c in cases)
    market_rows = "\n".join(
        f'''            <tr>
              <td><a class="card__link" href="{esc(a['source'])}" target="_blank" rel="noopener">{esc(a['name'])}</a></td>
              <td><span class="badge badge--warn">需复核</span></td>
              <td class="mono">{esc(a['score'])}</td>
              <td class="mono">{esc(a['findingGroups'])}</td>
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
