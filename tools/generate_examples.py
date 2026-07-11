from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pptlint.model import load_deck
from pptlint.render import render_deck
from pptlint.report import build_report, write_reports
from pptlint.rules import audit_deck
from pptlint.scoring import score_findings
from tests.pptx_factory import slide_xml, write_pptx


ROOT = Path(__file__).resolve().parents[1]


def audit_example(source: Path, output: Path, profile: str) -> int:
    deck = load_deck(source)
    findings = audit_deck(deck, profile=profile)
    scores = score_findings(findings)
    report = build_report(
        deck,
        findings,
        scores,
        render_deck(deck, source=source, renderer="wireframe"),
        profile=profile,
    )
    write_reports(output, report)
    return scores.overall


def font(size: int, bold: bool = False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def demo_gif(good_score: int, bad_score: int) -> None:
    frames: list[Image.Image] = []
    messages = [
        ("$ pptlint check output.pptx", "One command. No upload. No model."),
        ("BLOCKED — fix before sending", f"Secondary trend score: {bad_score}/100"),
        ("Open the named slide", "See what can go wrong and how to fix it."),
        ("Run PPTLint again", "Check a separate edited copy."),
        (f"READY — score {good_score}/100", "The file is ready to hand off."),
    ]
    for index, (headline, detail) in enumerate(messages):
        image = Image.new("RGB", (1200, 680), "#f3efe6")
        draw = ImageDraw.Draw(image)
        draw.rectangle((42, 42, 1158, 638), fill="#111820")
        draw.text((88, 82), "PPTLINT / 0.3", font=font(24, True), fill="#db7751")
        draw.text((88, 238), headline, font=font(42, True), fill="#fffaf0")
        draw.text((88, 330), detail, font=font(28), fill="#b7c0c9")
        draw.rectangle((88, 518, 1112, 526), fill="#2c3945")
        draw.rectangle((88, 518, 88 + round(1024 * (index + 1) / len(messages)), 526), fill="#db7751")
        frames.append(image)
    output = ROOT / "assets/pptlint-demo.gif"
    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output, save_all=True, append_images=frames[1:], duration=2000, loop=0, optimize=True)


def main() -> None:
    examples = ROOT / "examples"
    reports = examples / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    good = write_pptx(examples / "good-deck.pptx")
    bad = write_pptx(
        examples / "bad-deck.pptx",
        include_picture=True,
        slides=[
            slide_xml(
                title=None,
                body_size=900,
                body_fill="FFFFFF",
                body_text_color="F8F8F8",
                include_picture=True,
                picture_alt="",
            )
        ],
    )
    good_score = audit_example(good, reports / "good-deck", "baseline")
    bad_score = audit_example(bad, reports / "bad-deck", "ai-generated")
    demo_gif(good_score, bad_score)


if __name__ == "__main__":
    main()
