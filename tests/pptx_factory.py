from __future__ import annotations

import base64
import zipfile
from pathlib import Path


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>"""

PRESENTATION = """<?xml version="1.0" encoding="UTF-8"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>
</p:presentation>"""

PRESENTATION_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>"""


def slide_xml(
    *,
    title: str | None = "Quarterly Review",
    body_size: int = 1800,
    body_font: str = "Aptos",
    include_picture: bool = False,
    picture_alt: str = "",
    body_x: int = 914400,
    body_y: int = 1828800,
    body_w: int = 10363200,
    body_h: int = 3200400,
    body_fill: str | None = None,
    body_text_color: str | None = None,
    body_text: str | None = "Evidence-backed summary",
    hidden: bool = False,
    body_overflow: str | None = None,
    second_body: bool = False,
) -> str:
    title_shape = f"""
    <p:sp>
      <p:nvSpPr><p:cNvPr id="2" name="Title 1"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="609600" y="457200"/><a:ext cx="10972800" cy="914400"/></a:xfrm></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="3200"/><a:t>{title}</a:t></a:r></a:p></p:txBody>
    </p:sp>""" if title is not None else ""
    picture = f"""
    <p:pic>
      <p:nvPicPr><p:cNvPr id="4" name="Hero" descr="{picture_alt}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
      <p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
      <p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="12192000" cy="6858000"/></a:xfrm><a:prstGeom prst="rect"/></p:spPr>
    </p:pic>""" if include_picture else ""
    body_shape = f"""
    <p:sp>
      <p:nvSpPr><p:cNvPr id="3" name="Body 2"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="{body_x}" y="{body_y}"/><a:ext cx="{body_w}" cy="{body_h}"/></a:xfrm>{f'<a:solidFill><a:srgbClr val="{body_fill}"/></a:solidFill>' if body_fill else ''}</p:spPr>
      <p:txBody><a:bodyPr{f' vertOverflow="{body_overflow}"' if body_overflow else ''}/><a:lstStyle/><a:p><a:r><a:rPr sz="{body_size}" latin="{body_font}">{f'<a:solidFill><a:srgbClr val="{body_text_color}"/></a:solidFill>' if body_text_color else ''}</a:rPr><a:t>{body_text}</a:t></a:r></a:p></p:txBody>
    </p:sp>""" if body_text is not None else ""
    second_body_shape = f"""
    <p:sp>
      <p:nvSpPr><p:cNvPr id="5" name="Body overlap"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="{body_x + body_w // 4}" y="{body_y + body_h // 4}"/><a:ext cx="{body_w}" cy="{body_h}"/></a:xfrm></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="{body_size}" latin="{body_font}"/><a:t>Overlapping text</a:t></a:r></a:p></p:txBody>
    </p:sp>""" if second_body else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" show="{'0' if hidden else '1'}">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>
    {title_shape}
    {body_shape}
    {second_body_shape}
    {picture}
  </p:spTree></p:cSld>
</p:sld>"""


def write_pptx(
    path: Path,
    *,
    include_picture: bool = False,
    broken_relationship: bool = False,
    slides: list[str] | None = None,
    creator: str | None = None,
    include_comments: bool = False,
    empty_comments: bool = False,
    notes_text: str | None = None,
    external_url: str | None = None,
    slide_order: list[int] | None = None,
    slide_width: str = "12192000",
    slide_height: str = "6858000",
    omit_picture_content_type: bool = False,
    presentation_relationship_type: str = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
    presentation_relationship_target: str = "slides/slide1.xml",
) -> Path:
    slides = slides or [slide_xml(include_picture=include_picture)]
    slide_order = list(range(1, len(slides) + 1)) if slide_order is None else slide_order
    image_target = "../media/missing.png" if broken_relationship else "../media/image1.png"
    relationship_items = []
    if include_picture or broken_relationship:
        relationship_items.append(f'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{image_target}"/>')
    if notes_text:
        relationship_items.append('<Relationship Id="rId9" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide" Target="../notesSlides/notesSlide1.xml"/>')
    if external_url:
        relationship_items.append(f'<Relationship Id="rId10" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="{external_url}" TargetMode="External"/>')
    slide_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">""" + "".join(relationship_items) + "</Relationships>"
    overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index in range(1, len(slides) + 1)
    )
    content_types = CONTENT_TYPES.replace(
        '  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>',
        overrides,
    )
    if include_picture and not omit_picture_content_type:
        content_types = content_types.replace(
            "</Types>",
            '<Default Extension="png" ContentType="image/png"/></Types>',
        )
    slide_ids = "".join(f'<p:sldId id="{255 + index}" r:id="rId{slide_number}"/>' for index, slide_number in enumerate(slide_order, 1))
    presentation = PRESENTATION.replace('<p:sldId id="256" r:id="rId1"/>', slide_ids)
    presentation = presentation.replace('cx="12192000" cy="6858000"', f'cx="{slide_width}" cy="{slide_height}"')
    presentation_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">""" + "".join(
        f'<Relationship Id="rId{index}" Type="{presentation_relationship_type}" Target="{presentation_relationship_target if index == 1 else "slides/slide%d.xml" % index}"/>'
        for index in range(1, len(slides) + 1)
    ) + "</Relationships>"
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml", content_types)
        package.writestr("_rels/.rels", ROOT_RELS)
        package.writestr("ppt/presentation.xml", presentation)
        package.writestr("ppt/_rels/presentation.xml.rels", presentation_rels)
        for index, xml in enumerate(slides, 1):
            package.writestr(f"ppt/slides/slide{index}.xml", xml)
            package.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", slide_rels if index == 1 else slide_rels.replace("rId2", f"rId{index + 1}"))
        if include_picture and not broken_relationship:
            package.writestr(
                "ppt/media/image1.png",
                base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="),
            )
        if creator:
            package.writestr(
                "docProps/core.xml",
                f'''<?xml version="1.0" encoding="UTF-8"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>{creator}</dc:creator><cp:lastModifiedBy>{creator}</cp:lastModifiedBy></cp:coreProperties>''',
            )
        if include_comments:
            comment = "" if empty_comments else '<p:cm authorId="0" idx="1"><p:pos x="0" y="0"/><p:text>Review this</p:text></p:cm>'
            package.writestr(
                "ppt/comments/comment1.xml",
                f'<p:cmLst xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">{comment}</p:cmLst>',
            )
        if notes_text:
            package.writestr(
                "ppt/notesSlides/notesSlide1.xml",
                f'''<?xml version="1.0" encoding="UTF-8"?><p:notes xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>{notes_text}</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:notes>''',
            )
    return path
