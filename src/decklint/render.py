from __future__ import annotations

import base64
import io
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

from .model import DeckModel, Slide


@dataclass(frozen=True)
class RenderResult:
    requested: str
    used: str
    status: str
    detail: str
    previews: list[str]

    def metadata(self) -> dict[str, str]:
        return {"requested": self.requested, "used": self.used, "status": self.status, "detail": self.detail}


def _data_uri(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _wireframe(deck: DeckModel, slide: Slide) -> str:
    width = 960
    height = max(1, round(width * deck.height / deck.width))
    image = Image.new("RGB", (width, height), "#f7f5ef")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    scale_x = width / deck.width
    scale_y = height / deck.height
    for shape in slide.shapes:
        box = (
            round(shape.bbox.x * scale_x),
            round(shape.bbox.y * scale_y),
            round((shape.bbox.x + shape.bbox.w) * scale_x),
            round((shape.bbox.y + shape.bbox.h) * scale_y),
        )
        if shape.kind == "picture":
            draw.rectangle(box, fill="#d7dce2", outline="#7b8794", width=2)
            draw.line((box[0], box[1], box[2], box[3]), fill="#9aa5b1", width=2)
            draw.line((box[0], box[3], box[2], box[1]), fill="#9aa5b1", width=2)
        else:
            fill = f"#{shape.fill_color}" if shape.fill_color and len(shape.fill_color) == 6 else "#ffffff"
            draw.rectangle(box, fill=fill, outline="#a8a39a", width=1)
        if shape.text:
            text = shape.text if len(shape.text) <= 80 else shape.text[:77] + "..."
            draw.text((box[0] + 6, box[1] + 5), text, fill="#172033", font=font)
    draw.rectangle((0, 0, width - 1, height - 1), outline="#3b424a", width=2)
    return _data_uri(image)


def _wireframe_previews(deck: DeckModel) -> list[str]:
    return [_wireframe(deck, slide) for slide in deck.slides]


def _libreoffice_previews(source: Path, soffice: str) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="decklint-render-") as temp:
        temp_path = Path(temp)
        profile = (temp_path / "profile").resolve().as_uri()
        completed = subprocess.run(
            [
                soffice,
                "--headless",
                "--nologo",
                "--nodefault",
                "--nofirststartwizard",
                "--norestore",
                f"-env:UserInstallation={profile}",
                "--convert-to",
                "pdf:impress_pdf_Export",
                "--outdir",
                str(temp_path),
                str(source.resolve()),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        pdf_path = temp_path / f"{source.stem}.pdf"
        if completed.returncode != 0 or not pdf_path.is_file():
            message = (completed.stderr or completed.stdout or "LibreOffice did not create a PDF").strip()
            raise RuntimeError(message[:300])
        document = pdfium.PdfDocument(pdf_path)
        previews: list[str] = []
        try:
            for page in document:
                bitmap = page.render(scale=1.5)
                previews.append(_data_uri(bitmap.to_pil().convert("RGB")))
        finally:
            document.close()
        return previews


def render_deck(
    deck: DeckModel,
    *,
    source: Path,
    renderer: str = "auto",
    soffice_path: str | None = None,
) -> RenderResult:
    if renderer not in {"auto", "wireframe", "libreoffice"}:
        raise ValueError(f"Unsupported renderer: {renderer}")
    if renderer == "wireframe":
        return RenderResult(renderer, "wireframe", "ok", "", _wireframe_previews(deck))
    soffice = soffice_path if soffice_path is not None else shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice or not Path(soffice).is_file():
        return RenderResult(
            renderer,
            "wireframe",
            "degraded",
            "LibreOffice was unavailable; structural wireframes were used.",
            _wireframe_previews(deck),
        )
    try:
        previews = _libreoffice_previews(source, soffice)
        if len(previews) != len(deck.slides):
            raise RuntimeError(f"LibreOffice rendered {len(previews)} pages for {len(deck.slides)} slides")
        return RenderResult(renderer, "libreoffice", "ok", "", previews)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        safe_detail = str(exc).replace(str(source.resolve()), source.name)
        return RenderResult(
            renderer,
            "wireframe",
            "degraded",
            f"LibreOffice rendering failed; structural wireframes were used: {safe_detail[:240]}",
            _wireframe_previews(deck),
        )
