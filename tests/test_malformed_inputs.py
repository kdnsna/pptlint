from __future__ import annotations

import struct
import zipfile
from pathlib import Path

import pytest

from decklint.cli import main

from .pptx_factory import slide_xml, write_pptx


def corrupt_stored_entry_crc(path: Path, entry_name: str) -> None:
    with zipfile.ZipFile(path) as package:
        info = package.getinfo(entry_name)
        assert info.compress_type == zipfile.ZIP_STORED
        header_offset = info.header_offset
    with path.open("r+b") as stream:
        stream.seek(header_offset)
        header = stream.read(30)
        fields = struct.unpack("<IHHHHHIIIHH", header)
        filename_length, extra_length = fields[-2:]
        data_offset = header_offset + 30 + filename_length + extra_length
        stream.seek(data_offset)
        original = stream.read(1)
        stream.seek(data_offset)
        stream.write(bytes([original[0] ^ 0x01]))


@pytest.mark.parametrize(
    ("width", "height"),
    [("0", "6858000"), ("12192000", "0"), ("not-a-number", "6858000")],
)
def test_invalid_slide_dimensions_return_two_without_traceback(
    tmp_path: Path, capsys, width: str, height: str
) -> None:
    source = write_pptx(tmp_path / "bad-size.pptx", slide_width=width, slide_height=height)

    exit_code = main(["audit", str(source), "--renderer", "wireframe", "--output", str(tmp_path / "report")])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Traceback" not in captured.err


def test_crc_corruption_returns_two_without_traceback(tmp_path: Path, capsys) -> None:
    source = write_pptx(tmp_path / "crc.pptx")
    corrupt_stored_entry_crc(source, "ppt/presentation.xml")

    exit_code = main(["audit", str(source), "--renderer", "wireframe", "--output", str(tmp_path / "report")])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Traceback" not in captured.err


def test_duplicate_package_part_returns_two(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "duplicate.pptx")
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(source, "a") as package:
            package.writestr("ppt/slides/slide1.xml", "<duplicate/>")

    assert main(["audit", str(source), "--renderer", "wireframe", "--output", str(tmp_path / "report")]) == 2


def test_extreme_slide_aspect_ratio_returns_two_without_rendering(tmp_path: Path, capsys) -> None:
    source = write_pptx(
        tmp_path / "extreme-aspect.pptx",
        slide_width="1",
        slide_height="100000000",
    )

    exit_code = main(["audit", str(source), "--renderer", "wireframe", "--output", str(tmp_path / "report")])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Traceback" not in captured.err
    assert not (tmp_path / "report.html").exists()


def test_extreme_group_coordinate_returns_two_without_traceback(tmp_path: Path, capsys) -> None:
    huge = "9" * 400
    grouped_slide = slide_xml().replace(
        '<p:grpSpPr/>',
        f'''<p:grpSpPr/><p:grpSp><p:nvGrpSpPr><p:cNvPr id="9" name="Group"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
        <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{huge}" cy="100"/><a:chOff x="0" y="0"/><a:chExt cx="100" cy="100"/></a:xfrm></p:grpSpPr>
        <p:sp><p:nvSpPr><p:cNvPr id="10" name="Child"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="10" cy="10"/></a:xfrm></p:spPr></p:sp></p:grpSp>''',
        1,
    )
    source = write_pptx(tmp_path / "huge-group.pptx", slides=[grouped_slide])

    exit_code = main(["audit", str(source), "--renderer", "wireframe", "--output", str(tmp_path / "report")])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Traceback" not in captured.err
