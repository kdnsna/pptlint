from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
CASE_PAGES = sorted((SITE / "lab" / "cases").glob("*.html"))
PRIMARY = [SITE / "index.html", SITE / "lab" / "index.html", SITE / "proof-loop" / "comparison.html", *CASE_PAGES]


class ContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.html_lang = ""
        self.title = False
        self.h1 = 0
        self.main = 0
        self.nav = 0
        self.canonical = ""
        self.meta: dict[tuple[str, str], str] = {}
        self.links: list[str] = []
        self.external_scripts: list[str] = []
        self.bad_buttons = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.html_lang = values.get("lang", "")
        elif tag == "title":
            self.title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "main":
            self.main += 1
        elif tag == "nav":
            self.nav += 1
        elif tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href", "")
        elif tag == "meta":
            if "name" in values:
                self.meta[("name", values["name"])] = values.get("content", "")
            if "property" in values:
                self.meta[("property", values["property"])] = values.get("content", "")
        elif tag == "a":
            self.links.append(values.get("href", ""))
        elif tag == "script" and values.get("src", "").startswith(("http://", "https://", "//")):
            self.external_scripts.append(values["src"])
        elif tag == "button" and not values.get("type"):
            self.bad_buttons += 1


def _resolve_internal(page: Path, href: str) -> Path | None:
    if not href or href.startswith(("#", "mailto:")):
        return None
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc:
        return None
    target = (page.parent / parsed.path).resolve()
    if parsed.path.endswith("/") or target.is_dir():
        target /= "index.html"
    return target


def check_page(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    parser = ContractParser()
    parser.feed(text)
    errors: list[str] = []
    label = str(path.relative_to(ROOT))
    required_meta = [
        ("name", "description"),
        ("property", "og:title"),
        ("property", "og:description"),
        ("property", "og:image"),
        ("name", "twitter:card"),
        ("name", "twitter:title"),
        ("name", "twitter:description"),
        ("name", "twitter:image"),
    ]
    if parser.html_lang != "zh-CN":
        errors.append(f"{label}: html lang must be zh-CN")
    if not parser.title or parser.h1 != 1 or parser.main != 1 or parser.nav < 1:
        errors.append(f"{label}: requires one title, H1, main, and at least one nav")
    if not parser.canonical.startswith("https://kdnsna.github.io/pptlint/"):
        errors.append(f"{label}: missing canonical")
    missing_meta = [key for key in required_meta if not parser.meta.get(key)]
    if missing_meta:
        errors.append(f"{label}: missing sharing metadata {missing_meta}")
    if parser.bad_buttons:
        errors.append(f"{label}: every button requires an explicit type")
    if parser.external_scripts:
        errors.append(f"{label}: external scripts are not allowed")
    if "/Users/" in text or "file://" in text:
        errors.append(f"{label}: contains a local absolute path")
    for href in parser.links:
        target = _resolve_internal(path, href)
        if target is not None and not target.exists():
            errors.append(f"{label}: broken internal link {href}")
    return errors


def main() -> int:
    errors: list[str] = []
    if len(CASE_PAGES) != 12:
        errors.append(f"Expected 12 case pages, found {len(CASE_PAGES)}")
    for page in PRIMARY:
        errors.extend(check_page(page))
    sitemap = (SITE / "sitemap.xml").read_text(encoding="utf-8")
    required_urls = {
        "https://kdnsna.github.io/pptlint/",
        "https://kdnsna.github.io/pptlint/lab/",
        "https://kdnsna.github.io/pptlint/proof-loop/comparison.html",
        *{
            f"https://kdnsna.github.io/pptlint/lab/cases/{page.name}"
            for page in CASE_PAGES
        },
    }
    missing = sorted(url for url in required_urls if f"<loc>{url}</loc>" not in sitemap)
    if missing:
        errors.append(f"sitemap.xml is missing: {missing}")
    if "/benchmark/" in sitemap:
        errors.append("sitemap.xml must not promote the pending benchmark")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in PRIMARY)
    for value in ("83 → 100", "103", "21", "3", "0"):
        if value not in combined:
            errors.append(f"Public pages are missing Proof value: {value}")
    if errors:
        raise SystemExit("Public site contract failed:\n- " + "\n- ".join(errors))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
