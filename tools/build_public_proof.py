from __future__ import annotations

import argparse
import json
from pathlib import Path

from decklint.comparison_report import _render_comparison_html, build_comparison_report


ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "site" / "proof-loop"


def render_public_proof() -> str:
    before = json.loads((PROOF / "before.json").read_text(encoding="utf-8"))
    after = json.loads((PROOF / "after.json").read_text(encoding="utf-8"))
    comparison = build_comparison_report(before, after, threshold="high")
    html = _render_comparison_html(comparison)
    head = """
<meta name="description" content="同一份 9 页可编辑 PPTX 从 83 分到 100 分：103 项高置信问题已处理，21 项低置信提醒持续存在，新增 3 项低置信提示，新增高置信问题为 0。">
<link rel="canonical" href="https://kdnsna.github.io/pptlint/proof-loop/comparison.html">
<link rel="icon" href="../favicon.svg">
<meta property="og:type" content="website">
<meta property="og:title" content="PPTLint 真实 Proof Loop：83 → 100">
<meta property="og:description" content="公开修改前后 PPTX、完整报告与 JSON；100 分仍有低置信提醒需要确认。">
<meta property="og:url" content="https://kdnsna.github.io/pptlint/proof-loop/comparison.html">
<meta property="og:image" content="https://kdnsna.github.io/pptlint/assets/pptlint-before-after-hero.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="PPTLint 真实 Proof Loop：83 → 100">
<meta name="twitter:description" content="103 已处理，21 持续，3 个新增低置信，0 个新增高置信。">
<meta name="twitter:image" content="https://kdnsna.github.io/pptlint/assets/pptlint-before-after-hero.png">
<style>
.site-nav{background:#fff;border-bottom:1px solid #d0d5dd;padding:12px 24px;display:flex;align-items:center;gap:22px;position:sticky;top:0;z-index:20}.site-nav strong{font:900 16px ui-monospace,monospace;margin-right:auto}.site-nav a{color:#10233f;font-weight:700;text-decoration:none}.site-actions{margin:42px 0 0;background:#10233f;color:#fff;padding:26px}.site-actions h2{margin-top:0}.site-actions p{color:#d0d5dd}.site-actions__links{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}.site-actions__links a{background:#fff;color:#10233f;padding:9px 12px;text-decoration:none;font-weight:700}.site-actions code{display:block;background:#071426;padding:12px;overflow-wrap:anywhere}.review-explain{background:#fff3d6;border-left:5px solid #b54708;padding:16px;margin:22px 0}a:focus-visible{outline:3px solid #fdb022;outline-offset:3px}@media(max-width:620px){.site-nav{padding:10px 14px;gap:12px;overflow-x:auto}.site-nav a{white-space:nowrap;font-size:12px}.site-nav strong{font-size:14px}.site-actions{padding:20px}}
</style>
"""
    nav = """<nav class="site-nav" aria-label="站点导航"><strong>PPTLINT</strong><a href="../">首页</a><a href="../lab/">案例</a><a href="comparison.html" aria-current="page">Proof</a></nav>"""
    actions = """
<aside class="review-explain"><strong>为什么 100 分仍是“建议确认”？</strong><br>分数只扣除高置信问题。修改后仍有 21 项持续存在和 3 项新出现的低置信提醒，所以报告没有把 100 分解释成“所有问题为 0”。</aside>
<section class="site-actions" aria-labelledby="next-step"><h2 id="next-step">下载证据，或检查你自己的 PPT</h2><p>这些文件来自同一次固定规则检查；完整报告可能包含页面预览和文字，请像保护原 PPT 一样保护它。</p><div class="site-actions__links"><a href="before.pptx" download>修改前 PPTX</a><a href="after.pptx" download>修改后 PPTX</a><a href="before.json" download>修改前 JSON</a><a href="after.json" download>修改后 JSON</a><a href="comparison.json" download>对比 JSON</a><a href="../lab/">查看 12 个案例</a><a href="../">返回首页</a></div><code>uvx --refresh pptlint app</code></section>
"""
    html = html.replace("</head>", head + "</head>")
    html = html.replace("<body><main>", f"<body>{nav}<main>")
    html = html.replace("</main></body>", actions + "</main></body>")
    return html


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = PROOF / "comparison.html"
    expected = render_public_proof()
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != expected:
            raise SystemExit("Public Proof page is stale; run tools/build_public_proof.py")
    else:
        output.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
