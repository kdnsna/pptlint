from __future__ import annotations

import hashlib
import os
import posixpath
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as XML

from defusedxml import ElementTree as SafeXML
from defusedxml.common import DefusedXmlException

from .model import DeckLoadError, load_deck
from .rules import audit_deck


OPERATIONS = (
    "clear-personal-metadata",
    "remove-comments",
    "remove-speaker-notes",
)

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
}

for prefix, uri in NS.items():
    XML.register_namespace("" if prefix in {"rel", "ct"} else prefix, uri)


class CleanupError(ValueError):
    """Operational failure while creating a cleaned copy."""


class CleanupNotApplicable(CleanupError):
    """A requested operation had nothing to change."""


@dataclass(frozen=True)
class AppliedOperation:
    operation: str
    changed_parts: tuple[str, ...]
    change_count: int


@dataclass(frozen=True)
class CleanupResult:
    source: Path
    output: Path
    source_sha256: str
    output_sha256: str
    operations: tuple[AppliedOperation, ...]


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_xml(data: bytes, part: str):
    try:
        return SafeXML.fromstring(data)
    except (DefusedXmlException, XML.ParseError) as exc:
        raise CleanupError(f"Could not safely update XML part: {part}") from exc


def _serialize(root) -> bytes:
    return XML.tostring(root, encoding="utf-8", xml_declaration=True)


def _rels_source(name: str) -> str:
    if name == "_rels/.rels":
        return ""
    directory, filename = posixpath.split(name)
    if not directory.endswith("/_rels") or not filename.endswith(".rels"):
        return ""
    source_directory = directory[: -len("/_rels")]
    return posixpath.join(source_directory, filename[: -len(".rels")])


def _resolved_target(source: str, target: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target.lstrip("/")))


def _comment_parts(package: zipfile.ZipFile, names: set[str]) -> set[str]:
    parts = {
        name
        for name in names
        if name.lower().startswith("ppt/comments/")
        or posixpath.basename(name).lower() in {"commentauthors.xml", "authors.xml"}
    }
    for name in sorted(item for item in names if item.endswith(".rels")):
        root = _parse_xml(package.read(name), name)
        source = _rels_source(name)
        for relationship in root.findall("rel:Relationship", NS):
            kind = str(relationship.get("Type", "")).lower()
            if "comment" not in kind and not kind.endswith("/person"):
                continue
            target = str(relationship.get("Target", ""))
            if target and relationship.get("TargetMode") != "External":
                resolved = _resolved_target(source, target)
                if resolved in names:
                    parts.add(resolved)
    return parts


def _clear_metadata(data: bytes, name: str) -> tuple[bytes, int]:
    root = _parse_xml(data, name)
    paths = (
        ("dc:creator", "cp:lastModifiedBy")
        if name == "docProps/core.xml"
        else ("ep:Manager", "ep:Company")
    )
    changed = 0
    for path in paths:
        node = root.find(path, NS)
        if node is not None and (node.text or "").strip():
            node.text = None
            changed += 1
    return (_serialize(root), changed) if changed else (data, 0)


def _clear_notes(data: bytes, name: str) -> tuple[bytes, int]:
    root = _parse_xml(data, name)
    changed = 0
    for node in root.findall(".//a:t", NS):
        if (node.text or "").strip():
            node.text = None
            changed += 1
    return (_serialize(root), changed) if changed else (data, 0)


def _strip_comment_relationships(data: bytes, name: str, removed: set[str]) -> tuple[bytes, int]:
    root = _parse_xml(data, name)
    source = _rels_source(name)
    changed = 0
    for relationship in list(root.findall("rel:Relationship", NS)):
        kind = str(relationship.get("Type", "")).lower()
        target = str(relationship.get("Target", ""))
        resolved = _resolved_target(source, target) if target else ""
        if "comment" in kind or kind.endswith("/person") or resolved in removed:
            root.remove(relationship)
            changed += 1
    return (_serialize(root), changed) if changed else (data, 0)


def _strip_content_type_overrides(data: bytes, removed: set[str]) -> tuple[bytes, int]:
    root = _parse_xml(data, "[Content_Types].xml")
    changed = 0
    for override in list(root.findall("ct:Override", NS)):
        part = str(override.get("PartName", "")).lstrip("/")
        if part in removed:
            root.remove(override)
            changed += 1
    return (_serialize(root), changed) if changed else (data, 0)


def _reserve_output(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise CleanupError(f"Output already exists: {output.name}") from exc
    os.close(descriptor)


def create_cleanup_copy(source: Path, output: Path, operations: list[str]) -> CleanupResult:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if not source.is_file():
        raise CleanupError(f"Source PPTX not found: {source.name}")
    if output.suffix.lower() != ".pptx":
        raise CleanupError("Output must use the .pptx extension")
    if source == output:
        raise CleanupError("Output must be a different path from the source PPTX")
    if not operations:
        raise CleanupError("At least one --apply operation is required")
    unknown = sorted(set(operations) - set(OPERATIONS))
    if unknown:
        raise CleanupError(f"Unsupported cleanup operation: {', '.join(unknown)}")
    if len(set(operations)) != len(operations):
        raise CleanupError("Each cleanup operation may be requested only once")

    try:
        load_deck(source)
    except DeckLoadError as exc:
        raise CleanupError(str(exc)) from exc
    source_sha256 = sha256_path(source)
    _reserve_output(output)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.stem}.tmp.", suffix=".pptx", dir=output.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    os.chmod(temporary, 0o600)
    applied: dict[str, dict[str, object]] = {
        operation: {"parts": set(), "count": 0} for operation in operations
    }
    try:
        with zipfile.ZipFile(source, "r") as reader:
            names = set(reader.namelist())
            removed_comments = _comment_parts(reader, names) if "remove-comments" in operations else set()
            with zipfile.ZipFile(temporary, "w") as writer:
                for info in reader.infolist():
                    name = info.filename
                    if name in removed_comments:
                        record = applied["remove-comments"]
                        record["parts"].add(name)
                        record["count"] += 1
                        continue
                    data = reader.read(name)
                    if "clear-personal-metadata" in operations and name in {
                        "docProps/core.xml", "docProps/app.xml"
                    }:
                        data, count = _clear_metadata(data, name)
                        if count:
                            record = applied["clear-personal-metadata"]
                            record["parts"].add(name)
                            record["count"] += count
                    if "remove-speaker-notes" in operations and name.startswith(
                        "ppt/notesSlides/"
                    ) and name.endswith(".xml"):
                        data, count = _clear_notes(data, name)
                        if count:
                            record = applied["remove-speaker-notes"]
                            record["parts"].add(name)
                            record["count"] += count
                    if "remove-comments" in operations and name.endswith(".rels"):
                        data, count = _strip_comment_relationships(data, name, removed_comments)
                        if count:
                            record = applied["remove-comments"]
                            record["parts"].add(name)
                            record["count"] += count
                    if "remove-comments" in operations and name == "[Content_Types].xml":
                        data, count = _strip_content_type_overrides(data, removed_comments)
                        if count:
                            record = applied["remove-comments"]
                            record["parts"].add(name)
                            record["count"] += count
                    writer.writestr(info, data)

        not_applied = [operation for operation, record in applied.items() if not record["count"]]
        if not_applied:
            raise CleanupNotApplicable(
                f"Requested operation did not apply: {', '.join(not_applied)}"
            )
        try:
            temporary_deck = load_deck(temporary)
            audit_deck(temporary_deck, profile="baseline", scenario="present")
        except DeckLoadError as exc:
            raise CleanupError(f"Cleaned copy failed package validation: {exc}") from exc
        if sha256_path(source) != source_sha256:
            raise CleanupError("Source file changed during cleanup; output was not created")
        os.replace(temporary, output)
        result = CleanupResult(
            source=source,
            output=output,
            source_sha256=source_sha256,
            output_sha256=sha256_path(output),
            operations=tuple(
                AppliedOperation(
                    operation=operation,
                    changed_parts=tuple(sorted(record["parts"])),
                    change_count=int(record["count"]),
                )
                for operation, record in applied.items()
            ),
        )
        return result
    except Exception:
        temporary.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
        raise
