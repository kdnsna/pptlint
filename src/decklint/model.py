from __future__ import annotations

import hashlib
import math
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from .schema import BBox


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}

MAX_ENTRIES = 20_000
MAX_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
MAX_XML_BYTES = 10 * 1024 * 1024
MAX_SLIDE_DIMENSION = 100_000_000
MAX_SLIDE_ASPECT_RATIO = 100
MAX_GEOMETRY_COORDINATE = 1_000_000_000
MAX_TRANSFORMED_COORDINATE = 10_000_000_000
MAX_TRANSFORM_SCALE = 1_000_000
MAX_ROTATION_UNITS = 21_600_000
SLIDE_RELATIONSHIP_TYPES = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
    "http://purl.oclc.org/ooxml/officeDocument/relationships/slide",
}
SLIDE_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
}


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


@dataclass(frozen=True)
class CoordinateTransform:
    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    def then(self, child: "CoordinateTransform") -> "CoordinateTransform":
        """Return this transform composed after ``child`` (self ∘ child)."""
        result = CoordinateTransform(
            a=self.a * child.a + self.c * child.b,
            b=self.b * child.a + self.d * child.b,
            c=self.a * child.c + self.c * child.d,
            d=self.b * child.c + self.d * child.d,
            e=self.a * child.e + self.c * child.f + self.e,
            f=self.b * child.e + self.d * child.f + self.f,
        )
        result.validate()
        return result

    def validate(self) -> None:
        coefficients = (self.a, self.b, self.c, self.d)
        translations = (self.e, self.f)
        if not all(math.isfinite(value) and abs(value) <= MAX_TRANSFORM_SCALE for value in coefficients):
            raise DeckLoadError("Shape transform scale exceeds the safety limit")
        if not all(math.isfinite(value) and abs(value) <= MAX_TRANSFORMED_COORDINATE for value in translations):
            raise DeckLoadError("Shape transform translation exceeds the safety limit")

    def apply_point(self, x: int, y: int) -> tuple[float, float]:
        transformed = (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)
        if not all(
            math.isfinite(value) and abs(value) <= MAX_TRANSFORMED_COORDINATE
            for value in transformed
        ):
            raise DeckLoadError("Transformed shape geometry exceeds the safety limit")
        return transformed

    def apply(self, box: BBox) -> BBox:
        corners = (
            self.apply_point(box.x, box.y),
            self.apply_point(box.x + box.w, box.y),
            self.apply_point(box.x, box.y + box.h),
            self.apply_point(box.x + box.w, box.y + box.h),
        )
        xs = [point[0] for point in corners]
        ys = [point[1] for point in corners]
        left, top = min(xs), min(ys)
        right, bottom = max(xs), max(ys)
        return BBox(round(left), round(top), round(right - left), round(bottom - top))

    def compose_group(
        self,
        *,
        off: tuple[int, int],
        ext: tuple[int, int],
        child_off: tuple[int, int],
        child_ext: tuple[int, int],
        rotation: int = 0,
        flip_h: bool = False,
        flip_v: bool = False,
    ) -> "CoordinateTransform":
        if ext[0] <= 0 or ext[1] <= 0 or child_ext[0] <= 0 or child_ext[1] <= 0:
            raise DeckLoadError("Group extents must be positive")
        group_scale_x = ext[0] / child_ext[0]
        group_scale_y = ext[1] / child_ext[1]
        if (
            not math.isfinite(group_scale_x)
            or not math.isfinite(group_scale_y)
            or group_scale_x > MAX_TRANSFORM_SCALE
            or group_scale_y > MAX_TRANSFORM_SCALE
        ):
            raise DeckLoadError("Group scale exceeds the safety limit")
        group_translate_x = off[0] - child_off[0] * group_scale_x
        group_translate_y = off[1] - child_off[1] * group_scale_y
        child_to_frame = CoordinateTransform(
            a=group_scale_x,
            d=group_scale_y,
            e=group_translate_x,
            f=group_translate_y,
        )
        orientation = _orientation_transform(off, ext, rotation, flip_h, flip_v)
        return self.then(orientation.then(child_to_frame))


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
    orphan_slide_parts: list[str] = field(default_factory=list)


def _read_xml(package: zipfile.ZipFile, name: str):
    try:
        info = package.getinfo(name)
    except KeyError as exc:
        raise DeckLoadError(f"Required PPTX part is missing: {name}") from exc
    if info.file_size > MAX_XML_BYTES:
        raise DeckLoadError(f"XML part exceeds the {MAX_XML_BYTES}-byte safety limit: {name}")
    try:
        raw = package.read(name)
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise DeckLoadError(f"Could not read PPTX part: {name}") from exc
    try:
        return ET.fromstring(raw)
    except (ParseError, DefusedXmlException) as exc:
        raise DeckLoadError(f"Invalid XML in PPTX part: {name}") from exc


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _positive_dimension(value: str, name: str) -> int:
    dimension = _bounded_int(value, f"slide {name}", minimum=1, maximum=MAX_SLIDE_DIMENSION)
    if not 0 < dimension <= MAX_SLIDE_DIMENSION:
        raise DeckLoadError(f"Slide {name} must be between 1 and {MAX_SLIDE_DIMENSION} EMU")
    return dimension


def _bounded_int(value: str | None, name: str, *, minimum: int, maximum: int) -> int:
    text = "" if value is None else str(value)
    try:
        number = int(text)
    except (TypeError, ValueError) as exc:
        raise DeckLoadError(f"Invalid {name}: {text[:80]}") from exc
    if not minimum <= number <= maximum:
        raise DeckLoadError(f"{name.capitalize()} is outside the supported safety range")
    return number


def _geometry_int(value: str, name: str, *, extent: bool = False) -> int:
    return _bounded_int(
        value,
        name,
        minimum=0 if extent else -MAX_GEOMETRY_COORDINATE,
        maximum=MAX_GEOMETRY_COORDINATE,
    )


def _rotation(xfrm) -> int:
    return _bounded_int(
        xfrm.get("rot", "0"),
        "shape rotation",
        minimum=-MAX_ROTATION_UNITS,
        maximum=MAX_ROTATION_UNITS,
    )


def _orientation_transform(
    off: tuple[int, int],
    ext: tuple[int, int],
    rotation: int,
    flip_h: bool,
    flip_v: bool,
) -> CoordinateTransform:
    radians = math.radians(rotation / 60_000)
    cosine = math.cos(radians)
    sine = math.sin(radians)
    horizontal = -1.0 if flip_h else 1.0
    vertical = -1.0 if flip_v else 1.0
    a = cosine * horizontal
    b = sine * horizontal
    c = -sine * vertical
    d = cosine * vertical
    center_x = off[0] + ext[0] / 2
    center_y = off[1] + ext[1] / 2
    transform = CoordinateTransform(
        a=a,
        b=b,
        c=c,
        d=d,
        e=center_x - a * center_x - c * center_y,
        f=center_y - b * center_x - d * center_y,
    )
    transform.validate()
    return transform


def _bbox(node, transform: CoordinateTransform | None = None) -> BBox:
    xfrm = node.find(".//a:xfrm", NS)
    if xfrm is None:
        xfrm = node.find(".//p:xfrm", NS)
    if xfrm is None:
        return BBox(0, 0, 0, 0)
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is None:
        off = xfrm.find("p:off", NS)
    if ext is None:
        ext = xfrm.find("p:ext", NS)
    box = BBox(
        _geometry_int(off.get("x", "0"), "shape x") if off is not None else 0,
        _geometry_int(off.get("y", "0"), "shape y") if off is not None else 0,
        _geometry_int(ext.get("cx", "0"), "shape width", extent=True) if ext is not None else 0,
        _geometry_int(ext.get("cy", "0"), "shape height", extent=True) if ext is not None else 0,
    )
    orientation = _orientation_transform(
        (box.x, box.y),
        (box.w, box.h),
        _rotation(xfrm),
        xfrm.get("flipH") in {"1", "true"},
        xfrm.get("flipV") in {"1", "true"},
    )
    return (transform or CoordinateTransform()).then(orientation).apply(box)


def _colors(node, path: str) -> list[str]:
    colors: list[str] = []
    for color in node.findall(path, NS):
        value = color.get("val")
        if value:
            colors.append(value.upper())
    return colors


def _parse_shape(node, z_order: int, transform: CoordinateTransform, id_prefix: str = "") -> Shape:
    kind = "picture" if node.tag.endswith("}pic") else "graphic-frame" if node.tag.endswith("}graphicFrame") else "shape"
    c_nv_pr = node.find(".//p:cNvPr", NS)
    local_id = c_nv_pr.get("id", str(z_order + 1)) if c_nv_pr is not None else str(z_order + 1)
    shape_id = f"{id_prefix}{local_id}"
    name = c_nv_pr.get("name", f"Shape {shape_id}") if c_nv_pr is not None else f"Shape {shape_id}"
    alt_text = ""
    if c_nv_pr is not None:
        alt_text = c_nv_pr.get("descr", "") or c_nv_pr.get("title", "")
    text = " ".join(value.strip() for value in (n.text for n in node.findall(".//a:t", NS)) if value and value.strip())
    font_sizes = [
        _bounded_int(n.get("sz"), "font size", minimum=0, maximum=1_000_000) / 100
        for n in node.findall(".//a:rPr", NS)
        if n.get("sz")
    ]
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
        bbox=_bbox(node, transform),
        text=text,
        font_sizes=font_sizes,
        font_families=sorted(set(font_families)),
        fill_color=fill_colors[0] if fill_colors else None,
        text_colors=text_colors,
        alt_text=alt_text,
        placeholder_type=placeholder.get("type", "body") if placeholder is not None else None,
        z_order=z_order,
    )


def _point(node, name: str) -> tuple[int, int]:
    point = node.find(f"a:{name}", NS) if node is not None else None
    if point is None:
        return (0, 0)
    first = "x" if name in {"off", "chOff"} else "cx"
    second = "y" if name in {"off", "chOff"} else "cy"
    extent = name in {"ext", "chExt"}
    return (
        _geometry_int(point.get(first, "0"), f"group {first}", extent=extent),
        _geometry_int(point.get(second, "0"), f"group {second}", extent=extent),
    )


def _group_transform(node, parent: CoordinateTransform) -> CoordinateTransform:
    xfrm = node.find("p:grpSpPr/a:xfrm", NS)
    if xfrm is None:
        return parent
    return parent.compose_group(
        off=_point(xfrm, "off"),
        ext=_point(xfrm, "ext"),
        child_off=_point(xfrm, "chOff"),
        child_ext=_point(xfrm, "chExt"),
        rotation=_rotation(xfrm),
        flip_h=xfrm.get("flipH") in {"1", "true"},
        flip_v=xfrm.get("flipV") in {"1", "true"},
    )


def _flatten_shapes(shape_tree) -> list[Shape]:
    shapes: list[Shape] = []

    def visit(container, transform: CoordinateTransform, prefix: str) -> None:
        for node in list(container):
            if node.tag.endswith("}grpSp"):
                group_properties = node.find("p:nvGrpSpPr/p:cNvPr", NS)
                group_id = group_properties.get("id", "group") if group_properties is not None else "group"
                visit(node, _group_transform(node, transform), f"{prefix}{group_id}/")
            elif node.tag.endswith(("}sp", "}pic", "}graphicFrame")):
                shapes.append(_parse_shape(node, len(shapes), transform, prefix))

    visit(shape_tree, CoordinateTransform(), "")
    return shapes


def _relationship_part(source: str) -> str:
    directory, filename = posixpath.split(source)
    return posixpath.join(directory, "_rels", f"{filename}.rels")


def _resolved_target(source: str, target: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target)).lstrip("/")


def _relationship_items(package: zipfile.ZipFile, names: set[str], source: str) -> list[dict[str, str]]:
    rel_name = _relationship_part(source)
    if rel_name not in names:
        return []
    root = _read_xml(package, rel_name)
    return [
        {
            "id": relationship.get("Id", ""),
            "type": relationship.get("Type", ""),
            "target": relationship.get("Target", ""),
            "mode": relationship.get("TargetMode", ""),
        }
        for relationship in root.findall("rel:Relationship", NS)
    ]


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
    digest = _sha256_path(path)
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
        if len(names) != len(infos):
            raise DeckLoadError("PPTX contains duplicate package part names")
        if "[Content_Types].xml" not in names:
            raise DeckLoadError("Required PPTX part is missing: [Content_Types].xml")
        content_types = _read_xml(package, "[Content_Types].xml")
        declared_slide_parts = {
            override.get("PartName", "").lstrip("/")
            for override in content_types.findall("ct:Override", NS)
            if override.get("ContentType") in SLIDE_CONTENT_TYPES
        }
        presentation = _read_xml(package, "ppt/presentation.xml")
        slide_size = presentation.find("p:sldSz", NS)
        width = _positive_dimension(slide_size.get("cx", "12192000"), "width") if slide_size is not None else 12_192_000
        height = _positive_dimension(slide_size.get("cy", "6858000"), "height") if slide_size is not None else 6_858_000
        if max(width, height) / min(width, height) > MAX_SLIDE_ASPECT_RATIO:
            raise DeckLoadError(
                f"Slide aspect ratio exceeds the {MAX_SLIDE_ASPECT_RATIO}:1 safety limit"
            )
        package_slide_names = sorted(
            (name for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=lambda name: int(re.search(r"(\d+)", name).group(1)),
        )
        presentation_relationships = {
            relationship["id"]: relationship
            for relationship in _relationship_items(package, names, "ppt/presentation.xml")
        }
        slide_names: list[str] = []
        slide_list_broken: list[BrokenRelationship] = []
        relationship_id_attribute = f"{{{NS['r']}}}id"
        for slide_id in presentation.findall(".//p:sldId", NS):
            relationship_id = slide_id.get(relationship_id_attribute, "")
            relationship = presentation_relationships.get(relationship_id)
            if relationship is None:
                slide_list_broken.append(
                    BrokenRelationship(
                        "ppt/presentation.xml",
                        relationship_id,
                        "(presentation slide relationship is missing)",
                    )
                )
                continue
            if relationship["mode"] == "External":
                slide_list_broken.append(
                    BrokenRelationship(
                        "ppt/presentation.xml",
                        relationship_id,
                        f"(external slide target: {relationship['target']})",
                    )
                )
                continue
            if relationship["type"] not in SLIDE_RELATIONSHIP_TYPES:
                slide_list_broken.append(
                    BrokenRelationship(
                        "ppt/presentation.xml",
                        relationship_id,
                        f"(invalid slide relationship type: {relationship['type']})",
                    )
                )
                continue
            target = _resolved_target("ppt/presentation.xml", relationship["target"])
            if target not in package_slide_names or target not in declared_slide_parts:
                slide_list_broken.append(
                    BrokenRelationship(
                        "ppt/presentation.xml",
                        relationship_id,
                        f"(invalid slide part target: {target})",
                    )
                )
                continue
            if target in names:
                slide_names.append(target)
        orphan_slide_parts = sorted(set(package_slide_names) - set(slide_names))
        slides: list[Slide] = []
        for index, slide_name in enumerate(slide_names, 1):
            root = _read_xml(package, slide_name)
            shape_tree = root.find(".//p:spTree", NS)
            shapes = [] if shape_tree is None else _flatten_shapes(shape_tree)
            title_candidates = [shape.text for shape in shapes if shape.placeholder_type in {"title", "ctrTitle"} and shape.text]
            title = title_candidates[0] if title_candidates else next((shape.text for shape in shapes if shape.text), "")
            notes_text = ""
            for relationship in _relationship_items(package, names, slide_name):
                if relationship["type"].endswith("/notesSlide") and relationship["mode"] != "External":
                    notes_part = _resolved_target(slide_name, relationship["target"])
                    if notes_part in names:
                        notes_root = _read_xml(package, notes_part)
                        notes_text = " ".join(
                            value.strip()
                            for value in (node.text for node in notes_root.findall(".//a:t", NS))
                            if value and value.strip()
                        )
                    break
            slides.append(
                Slide(
                    index=index,
                    part_name=slide_name,
                    title=title,
                    shapes=shapes,
                    hidden=root.get("show") == "0",
                    notes_text=notes_text,
                )
            )
        broken, external = _scan_relationships(package, names)
        broken.extend(slide_list_broken)
        metadata: dict[str, str] = {}
        if "docProps/core.xml" in names:
            core = _read_xml(package, "docProps/core.xml")
            for key, path_expr in {"creator": "dc:creator", "lastModifiedBy": "cp:lastModifiedBy"}.items():
                value = core.find(path_expr, NS)
                if value is not None and value.text:
                    metadata[key] = value.text.strip()
        comments_count = 0
        for comment_part in sorted(name for name in names if name.startswith("ppt/comments/") and name.endswith(".xml")):
            comment_root = _read_xml(package, comment_part)
            comments_count += sum(
                1
                for element in comment_root.iter()
                if element.tag.rsplit("}", 1)[-1] in {"cm", "comment"}
            )
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
            orphan_slide_parts=orphan_slide_parts,
        )
