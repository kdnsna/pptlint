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


def slide_markup() -> str:
    return '<div class="slide"><span class="line"></span><span class="line short"></span><span class="line"></span><div class="chart"><i style="height:42%"></i><i></i><i></i></div></div>'


def case_card(case: dict[str, object], *, linked: bool = True) -> str:
    link = f'cases/{esc(case["slug"])}.html' if linked else "../index.html"
    link_label = "查看检查依据和处理过程 →" if linked else "← 返回全部案例"
    return f'''<article class="case-card" data-category="{esc(case["category"])}" data-visual="{esc(case["visual"])}">
  <div class="case-copy"><span class="tag">可控演示 · {esc(case["category"])}</span><h2>{esc(case["title"])}</h2><p>{esc(case["scene"])}</p></div>
  <div class="comparison">
    <section class="state before"><div class="state-head"><span>修改前</span><span>{esc(case["scoreBefore"])} 分</span></div>{slide_markup()}</section>
    <section class="state after"><div class="state-head"><span>修改后</span><span>{esc(case["scoreAfter"])} 分</span></div>{slide_markup()}</section>
  </div>
  <div class="case-footer"><div><strong>发现</strong>{esc(case["before"])}</div><div><strong>处理</strong>{esc(case["after"])}</div></div>
  <a class="case-link" href="{link}">{link_label}</a>
</article>'''


def head(*, title: str, description: str, prefix: str = "") -> str:
    canonical = "https://kdnsna.github.io/pptlint/lab/" + prefix
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="{'../../' if prefix else '../'}favicon.svg" type="image/svg+xml"><meta name="description" content="{esc(description)}"><link rel="canonical" href="{canonical}"><meta property="og:type" content="website"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:image" content="https://kdnsna.github.io/pptlint/assets/pptlint-before-after-hero.png"><meta name="twitter:card" content="summary_large_image"><title>{esc(title)}</title><link rel="stylesheet" href="{'../' if prefix else ''}lab.css"></head><body>'''


def topbar(*, prefix: str = "") -> str:
    return f'''<header class="topbar shell"><a class="brand" href="{prefix}../"><span>PPT</span>LINT</a><nav><a href="{prefix}../">产品首页</a><a href="{prefix}../proof-loop/comparison.html">真实 Proof Loop</a><a href="https://github.com/kdnsna/pptlint">GitHub</a></nav></header>'''


def build_index(data: dict[str, object]) -> str:
    cases = data["cases"]
    audits = data["marketAudits"]
    assert isinstance(cases, list) and isinstance(audits, list)
    categories = ["全部", *dict.fromkeys(str(case["category"]) for case in cases)]
    filters = "".join(
        f'<button class="filter{" active" if category == "全部" else ""}" data-category="{esc(category)}">{esc(category)}</button>'
        for category in categories
    )
    cards = "\n".join(case_card(case) for case in cases)
    market_cards = "\n".join(
        f'''<article class="market-card"><span class="tag">公开样本实测</span><div class="score">{esc(audit["score"])}</div><h3>{esc(audit["name"])}</h3><p>{esc(audit["findingGroups"])} 个问题组 · {esc(audit["note"])}</p><p><code>sha256 {esc(str(audit["sha256"])[:12])}…</code></p><a href="{esc(audit["sourceFile"])}">查看准确样本 ↗</a></article>'''
        for audit in audits
    )
    return head(title="PPTLint 交付案例实验室", description="12 个一眼看懂的 PowerPoint 交付风险前后对比，以及热门 AI PPT 项目的公开样本实测。") + topbar() + f'''<main class="shell">
<section class="hero"><div><span class="kicker">PPTLint Delivery Lab · v{esc(data["version"])}</span><h1>好看的 PPT，<br>也可能还不能直接发。</h1><p>这里不评审美，也不替你改文件。我们把会议室、换电脑、可编辑交接和隐私外发中的真实风险，做成 12 个一眼能懂的前后对比。</p></div><aside class="hero-proof"><strong>12 + 4</strong><span>12 个可控前后演示 · 4 个热门开源项目样本实测</span><div class="fine">本地 · 只读 · 不上传 · 不调用模型</div></aside></section>
<section><div class="section-head"><div><span class="kicker">Before / After</span><h2>先看会出什么事，再看怎么处理</h2></div><p>每个案例都公开检查规则、处理边界和复检方式。100 分只代表这些规则通过，不代表审美满分或绝对零风险。</p></div><div class="filters">{filters}</div><div class="case-grid">{cards}</div></section>
<section class="market"><div class="section-head"><div><span class="kicker">Market compatibility</span><h2>优秀 AI PPT，PPTLint 还能看什么？</h2></div><p>审美已经很好时，价值从“挑版式”转向“交付验收”：观看距离、文件完整性、可编辑对象、隐私残留和跨电脑稳定性。</p></div><div class="market-grid">{market_cards}</div><p class="disclosure">公开样本实测只描述 PPTLint 在默认“会议室演示”场景下的规则结果，不代表对项目整体质量的排名。样本版权归原项目，本站仅链接来源，不提供第三方文件下载。</p></section>
<section class="method"><div class="section-head"><div><span class="kicker">Evidence boundary</span><h2>真实证据和情境演示，分开说</h2></div></div><p class="disclosure">上方 12 个案例是为解释单一风险而制作的可控演示，不伪装成客户案例；公开的 49 → 100 Proof Loop 才是可下载、可复核的真实九页 PPTX 改造证据。</p></section>
<section class="cta"><div><h2>自己的 PPT，发出去前先查一次。</h2><p>一分钟生成离线 HTML 报告；原文件保持不变。</p></div><div class="buttons"><a class="button primary" href="https://github.com/kdnsna/pptlint#quick-start">安装 PPTLint</a><a class="button" href="../proof-loop/comparison.html">打开真实对比</a></div></section></main><footer class="shell">PPTLint v{esc(data["version"])} · MIT · Updated {esc(data["updated"])}</footer><script src="lab.js"></script></body></html>'''


def build_case_page(case: dict[str, object]) -> str:
    description = f'{case["title"]}：{case["scene"]}'
    return head(title=f'{case["title"]} · PPTLint 案例', description=description, prefix=f'cases/{case["slug"]}.html') + topbar(prefix="../") + f'''<main class="case-page shell"><span class="kicker">{esc(case["category"])} · Controlled demonstration</span><h1>{esc(case["title"])}</h1><p class="lead">{esc(case["scene"])}</p>{case_card(case, linked=False)}<section class="steps"><article><strong>01 · PPTLint 发现</strong><p>{esc(case["before"])}</p></article><article><strong>02 · 人工处理</strong><p>{esc(case["after"])}</p></article><article><strong>03 · 同场景复检</strong><p><code>pptlint check deck.pptx --scenario present</code></p></article></section><p class="disclosure">规则：<code>{esc(case["rule"])}</code>。这是用于解释单一风险的可控演示，不是客户证言。分数只代表规则检查结果；PPTLint 不自动修改文件，也不把审美偏好冒充成错误。</p><section class="cta"><div><h2>查看另外 11 个交付案例</h2><p>从投屏事故，到隐私外发和可编辑交接。</p></div><div class="buttons"><a class="button primary" href="../index.html">返回案例实验室</a><a class="button" href="https://github.com/kdnsna/pptlint">GitHub</a></div></section></main><footer class="shell">PPTLint · Local, read-only PowerPoint preflight</footer></body></html>'''


def outputs() -> dict[Path, str]:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if len(cases) != 12:
        raise ValueError("The case lab must contain exactly 12 completed cases")
    built = {LAB / "index.html": build_index(data)}
    for case in cases:
        built[LAB / "cases" / f'{case["slug"]}.html'] = build_case_page(case)
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
