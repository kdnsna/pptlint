from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from defusedxml import ElementTree as ET

from .schema import BBox


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
}

MAX_ENTRIES = 20_000
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
MAX_XML_BYTES = 10 * 1024 * 1024


class DeckLoadError(ValueError):
    """Raised when an input cannot be treated as a safe PPTX package."""


@dataclass
class Shape:
    shape_id: str
    name: str
    kind: str
    bbox: BBox
    text: str = ""
    font_sizes: list[float] = field(default_factory=list)
    font_families: list[str] = field(default_factory=list)
    fill_color: str | None = None
    text_colors: list[str] = field(default_factory=list)
    alt_text: str = ""
    placeholder_type: str | None = None
    z_order: int = 0
    media_target: str | None = None


@dataclass
class Slide:
    index: int
    part_name: str
    title: str
    shapes: list[Shape]
    hidden: bool = False
    notes_text: str = ""


@dataclass
class BrokenRelationship:
    source: str
    relationship_id: str
    target: str


@dataclass
class DeckModel:
    filename: str
    sha256: str
    width: int
    height: int
    slides: list[Slide]
    package_names: set[str]
    broken_relationships: list[BrokenRelationship] = field(default_factory=list)
    external_relationships: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    comments_count: int = 0


def _read_xml(package: zipfile.ZipFile, name: str):
    try:
        info = package.getinfo(name)
    except KeyError as exc:
        raise DeckLoadError(f"Required PPTX part is missing: {name}") from exc
    if info.file_size > MAX_XML_BYTES:
        raise DeckLoadError(f"XML part exceeds the {MAX_XML_BYTES}-byte safety limit: {name}")
    try:
        return ET.fromstring(package.read(name))
    except ET.ParseError as exc:
        raise DeckLoadError(f"Invalid XML in PPTX part: {name}") from exc


def _bbox(node) -> BBox:
    xfrm = node.find(".//a:xfrm", NS)
    if xfrm is None:
        return BBox(0, 0, 0, 0)
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    return BBox(
        int(off.get("x", "0")) if off is not None else 0,
        int(off.get("y", "0")) if off is not None else 0,
        int(ext.get("cx", "0")) if ext is not None else 0,
        int(ext.get("cy", "0")) if ext is not None else 0,
    )


def _colors(node, path: str) -> list[str]:
    colors: list[str] = []
    for color in node.findall(path, NS):
        value = color.get("val")
        if value:
            colors.append(value.upper())
    return colors


def _parse_shape(node, z_order: int) -> Shape:
    kind = "picture" if node.tag.endswith("}pic") else "graphic-frame" if node.tag.endswith("}graphicFrame") else "shape"
    c_nv_pr = node.find(".//p:cNvPr", NS)
    shape_id = c_nv_pr.get("id", str(z_order + 1)) if c_nv_pr is not None else str(z_order + 1)
    name = c_nv_pr.get("name", f"Shape {shape_id}") if c_nv_pr is not None else f"Shape {shape_id}"
    alt_text = ""
    if c_nv_pr is not None:
        alt_text = c_nv_pr.get("descr", "") or c_nv_pr.get("title", "")
    text = " ".join(value.strip() for value in (n.text for n in node.findall(".//a:t", NS)) if value and value.strip())
    font_sizes = [int(n.get("sz")) / 100 for n in node.findall(".//a:rPr", NS) if n.get("sz")]
    font_families: list[str] = []
    for run_properties in node.findall(".//a:rPr", NS):
        if run_properties.get("latin"):
            font_families.append(run_properties.get("latin"))
        latin = run_properties.find("a:latin", NS)
        if latin is not None and latin.get("typeface"):
            font_families.append(latin.get("typeface"))
    placeholder = node.find(".//p:ph", NS)
    fill_colors = _colors(node, ".//p:spPr/a:solidFill/a:srgbClr")
    text_colors = _colors(node, ".//a:rPr/a:solidFill/a:srgbClr")
    return Shape(
        shape_id=shape_id,
        name=name,
        kind=kind,
        bbox=_bbox(node),
        text=text,
        font_sizes=font_sizes,
        font_families=sorted(set(font_families)),
        fill_color=fill_colors[0] if fill_colors else None,
        text_colors=text_colors,
        alt_text=alt_text,
        placeholder_type=placeholder.get("type", "body") if placeholder is not None else None,
        z_order=z_order,
    )


def _relationship_part(source: str) -> str:
    directory, filename = posixpath.split(source)
    return posixpath.join(directory, "_rels", f"{filename}.rels")


def _resolved_target(source: str, target: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target)).lstrip("/")


def _scan_relationships(package: zipfile.ZipFile, names: set[str]) -> tuple[list[BrokenRelationship], list[str]]:
    broken: list[BrokenRelationship] = []
    external: list[str] = []
    for rel_name in sorted(name for name in names if name.endswith(".rels")):
        root = _read_xml(package, rel_name)
        if rel_name == "_rels/.rels":
            source = ""
        else:
            source = rel_name.replace("/_rels/", "/")[:-5]
        for relationship in root.findall("rel:Relationship", NS):
            target = relationship.get("Target", "")
            if relationship.get("TargetMode") == "External":
                external.append(target)
                continue
            resolved = _resolved_target(source, target)
            if resolved not in names:
                broken.append(BrokenRelationship(source, relationship.get("Id", ""), resolved))
    return broken, external


def load_deck(path: Path) -> DeckModel:
    path = Path(path)
    if not path.is_file() or path.suffix.lower() != ".pptx":
        raise DeckLoadError(f"PPTX file not found: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        package = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise DeckLoadError(f"Not a valid PPTX ZIP package: {path.name}") from exc
    with package:
        infos = package.infolist()
        if len(infos) > MAX_ENTRIES:
            raise DeckLoadError(f"PPTX contains more than {MAX_ENTRIES} package entries")
        if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
            raise DeckLoadError(f"PPTX exceeds the {MAX_UNCOMPRESSED_BYTES}-byte uncompressed safety limit")
        names = {info.filename for info in infos}
        if "[Content_Types].xml" not in names:
            raise DeckLoadError("Required PPTX part is missing: [Content_Types].xml")
        presentation = _read_xml(package, "ppt/presentation.xml")
        slide_size = presentation.find("p:sldSz", NS)
        width = int(slide_size.get("cx", "12192000")) if slide_size is not None else 12_192_000
        height = int(slide_size.get("cy", "6858000")) if slide_size is not None else 6_858_000
        slide_names = sorted(
            (name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda name: int(re.search(r"(\d+)", name).group(1)),
        )
        slides: list[Slide] = []
        for index, slide_name in enumerate(slide_names, 1):
            root = _read_xml(package, slide_name)
            shape_tree = root.find(".//p:spTree", NS)
            shapes = [] if shape_tree is None else [
                _parse_shape(node, z_order)
                for z_order, node in enumerate(list(shape_tree))
                if node.tag.endswith(("}sp", "}pic", "}graphicFrame"))
            ]
            title_candidates = [shape.text for shape in shapes if shape.placeholder_type in {"title", "ctrTitle"} and shape.text]
            title = title_candidates[0] if title_candidates else next((shape.text for shape in shapes if shape.text), "")
            slides.append(Slide(index=index, part_name=slide_name, title=title, shapes=shapes, hidden=root.get("show") == "0"))
        broken, external = _scan_relationships(package, names)
        metadata: dict[str, str] = {}
        if "docProps/core.xml" in names:
            core = _read_xml(package, "docProps/core.xml")
            for key, path_expr in {"creator": "dc:creator", "lastModifiedBy": "cp:lastModifiedBy"}.items():
                value = core.find(path_expr, NS)
                if value is not None and value.text:
                    metadata[key] = value.text.strip()
        comments_count = sum(1 for name in names if re.fullmatch(r"ppt/comments/comment\d+\.xml", name))
        return DeckModel(
            filename=path.name,
            sha256=digest,
            width=width,
            height=height,
            slides=slides,
            package_names=names,
            broken_relationships=broken,
            external_relationships=external,
            metadata=metadata,
            comments_count=comments_count,
        )

