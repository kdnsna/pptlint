from __future__ import annotations

from dataclasses import dataclass

from .schema import Finding


BLOCKER_RULES = {
    "integrity.broken-relationship",
    "integrity.empty-deck",
    "integrity.missing-content-type",
    "privacy.comments",
    "privacy.external-relationship",
    "readability.off-canvas-text",
    "readability.text-overlap",
}

RULE_IMPACTS = {
    "integrity.broken-relationship": "PowerPoint may repair the file, omit content, or refuse to open it.",
    "integrity.empty-deck": "The file contains no slide that can be presented.",
    "integrity.missing-content-type": "PowerPoint may repair or omit the undeclared package part.",
    "privacy.comments": "Internal review comments can leave the organization with the file.",
    "privacy.external-relationship": "The presentation depends on or exposes an external URL or file.",
    "privacy.speaker-notes": "Speaker notes may contain information that was not intended for recipients.",
    "readability.off-canvas-text": "Audience-visible text may be clipped or disappear during presentation.",
    "readability.text-overlap": "Two text regions may cover each other in the delivered slide.",
    "readability.small-font": "The audience may not be able to read the affected text at presentation distance.",
    "readability.low-contrast": "The affected text may be unreadable on a projector or low-quality display.",
    "editability.full-slide-image": "Important content cannot be edited as native PowerPoint objects.",
    "privacy.hidden-slide": "A hidden slide can still leave the organization inside the delivered file.",
    "privacy.personal-metadata": "The file can reveal author or editing identity that recipients do not need.",
    "readability.text-clipping-risk": "The final lines may be cut off when the slide is opened or presented.",
    "readability.font-portability-risk": "A font unavailable on another computer can change line breaks and spacing.",
    "readability.dense-text": "The audience may not have enough time or distance to read this amount of text.",
    "readability.blank-slide": "An unintended blank page can interrupt the presentation or confuse recipients.",
    "readability.unusual-aspect-ratio": "The deck may be cropped or surrounded by large bars on common displays.",
    "accessibility.missing-alt-text": "People using assistive technology may not understand the image.",
    "accessibility.missing-title": "The slide is harder to navigate, review, and hand over without a clear title.",
    "accessibility.reading-order-risk": "Assistive technology may read the slide in a confusing order.",
    "consistency.font-outlier": "An accidental font change can make the deck look unfinished or reflow elsewhere.",
    "consistency.repeated-layout": "Repeated structure may make the story difficult to scan and follow.",
    "integrity.orphan-slide-part": "Unused slide data remains in the package and should be reviewed before delivery.",
}

RULE_FIX_STEPS = {
    "integrity.broken-relationship": [
        "Open a duplicate of the file in PowerPoint and note any repair warning.",
        "Restore the missing media or object, then save the duplicate as a new PPTX.",
        "Run PPTLint again and confirm that the broken relationship is gone.",
    ],
    "integrity.empty-deck": [
        "Open the source project or template used to generate the presentation.",
        "Export at least one valid slide to a new PPTX.",
        "Run PPTLint again before delivery.",
    ],
    "privacy.comments": [
        "In PowerPoint, open Review and inspect every comment.",
        "Delete comments that must not leave the organization.",
        "Save a delivery copy and run PPTLint again.",
    ],
    "privacy.external-relationship": [
        "Open File > Info and inspect linked files or external content.",
        "Embed, remove, or explicitly approve the external reference.",
        "Save a delivery copy and run PPTLint again.",
    ],
    "privacy.speaker-notes": [
        "Open Notes view and review the notes on the reported slide.",
        "Remove confidential or draft-only text from the delivery copy.",
        "Run PPTLint again to confirm the intended result.",
    ],
    "readability.off-canvas-text": [
        "Open the reported slide and select the highlighted text box.",
        "Move or resize it until the complete box remains inside the slide canvas.",
        "Run PPTLint again and inspect the rendered preview.",
    ],
    "readability.text-overlap": [
        "Open the reported slide and inspect the two highlighted text areas.",
        "Move, resize, or shorten the content so neither area covers the other.",
        "Run PPTLint again and inspect the rendered preview.",
    ],
    "readability.text-clipping-risk": [
        "Open the reported text box and check its final line at 100% zoom.",
        "Increase the box height, reduce the text, or allow text to resize safely.",
        "Save a delivery copy and run PPTLint again.",
    ],
    "readability.font-portability-risk": [
        "Confirm that recipients are expected to have the reported font.",
        "Replace it with an approved portable font or embed fonts when licensing permits.",
        "Reopen the delivery copy on another computer and run PPTLint again.",
    ],
    "readability.small-font": [
        "View the reported slide at the size used in the meeting room.",
        "Increase the text size or reduce the amount of content.",
        "Run PPTLint again and inspect the rendered preview.",
    ],
    "readability.low-contrast": [
        "View the highlighted text against its actual background.",
        "Darken the text, lighten the background, or add a solid backing shape.",
        "Run PPTLint again and inspect the rendered preview.",
    ],
    "editability.full-slide-image": [
        "Confirm whether the recipient must edit any text, number, chart, or shape on this slide.",
        "Rebuild required content as native PowerPoint objects in a delivery copy.",
        "Run PPTLint again and confirm the flattened-slide count.",
    ],
    "privacy.hidden-slide": [
        "Open Slide Sorter and review every hidden slide.",
        "Delete slides that must not leave the organization, or explicitly approve them.",
        "Save a delivery copy and run PPTLint again.",
    ],
    "privacy.personal-metadata": [
        "Open File > Info and inspect document properties.",
        "Remove personal information from the delivery copy when it is not needed.",
        "Run PPTLint again and confirm that the metadata reminder is gone.",
    ],
}

ZH_IMPACTS = {
    "integrity.broken-relationship": "对方打开时，PowerPoint 可能修复文件、漏掉内容，甚至无法打开。",
    "integrity.empty-deck": "文件里没有可正常演示的页面。",
    "integrity.missing-content-type": "对方打开时，PowerPoint 可能修复或忽略这部分内容。",
    "privacy.comments": "内部修改意见可能跟着文件一起发给对方。",
    "privacy.external-relationship": "文件可能依赖外部网址或本地路径，也可能暴露不该外发的地址。",
    "privacy.speaker-notes": "讲者备注里可能留着只供内部使用的内容。",
    "privacy.hidden-slide": "隐藏页仍然保存在文件里，收件人可以找到。",
    "privacy.personal-metadata": "文件可能暴露作者或编辑者信息。",
    "readability.off-canvas-text": "投屏或打开文件时，观众可能看不到被挤到页面外的文字。",
    "readability.text-overlap": "两块文字可能互相遮挡，现场看起来像没有检查过。",
    "readability.text-clipping-risk": "换电脑或投屏后，文本框最后几行可能被截掉。",
    "readability.font-portability-risk": "对方电脑没有这个字体时，标题可能换行，整页位置也会变化。",
    "readability.small-font": "坐在会议室后排的人可能看不清这些字。",
    "readability.low-contrast": "投影变灰或环境较亮时，这些字可能看不清。",
    "readability.dense-text": "一页文字太多，观众来不及看完。",
    "readability.blank-slide": "意外空白页会打断汇报，也会让收件人误以为内容缺失。",
    "readability.unusual-aspect-ratio": "在常见屏幕上可能被裁切，或出现很宽的黑边。",
    "editability.full-slide-image": "整页像一张截图，对方想改一个数字也改不了。",
    "accessibility.missing-alt-text": "使用辅助阅读工具的人可能无法理解这张图片。",
    "accessibility.missing-title": "没有清楚标题时，别人难以浏览、复核和接手。",
    "accessibility.reading-order-risk": "辅助阅读工具可能按错误顺序读出内容。",
    "consistency.font-outlier": "意外混入的字体会让页面显得没收尾，换电脑时也可能变形。",
    "consistency.repeated-layout": "页面结构过度重复，观众不容易抓住重点。",
    "integrity.orphan-slide-part": "文件包里留着未使用的页面数据，外发前应确认。",
}

ZH_FIX_STEPS = {
    "privacy.comments": ["在 PowerPoint 的“审阅”中查看全部批注。", "删除不应外发的批注。", "另存交付副本，再运行一次 PPTLint。"],
    "privacy.external-relationship": ["在“文件 > 信息”中检查链接和外部内容。", "把内容嵌入文件、删除链接，或确认该链接可以外发。", "另存交付副本，再运行一次 PPTLint。"],
    "privacy.speaker-notes": ["打开报告所示页面的备注区。", "删除机密、草稿或只供内部使用的文字。", "再运行一次 PPTLint，确认提醒消失。"],
    "privacy.hidden-slide": ["在幻灯片浏览视图中查看全部隐藏页。", "删除不应外发的页面，或明确确认可以保留。", "另存交付副本，再运行一次 PPTLint。"],
    "privacy.personal-metadata": ["在“文件 > 信息”中查看文档属性。", "在交付副本中删除不需要的个人信息。", "再运行一次 PPTLint，确认提醒消失。"],
    "readability.off-canvas-text": ["打开报告所示页面并选中高亮文本框。", "移动或缩放文本框，让它完整留在页面内。", "再运行一次 PPTLint，并查看页面预览。"],
    "readability.text-overlap": ["打开报告所示页面，查看两块高亮文字。", "移动、缩放或精简内容，避免相互遮挡。", "再运行一次 PPTLint，并查看页面预览。"],
    "readability.text-clipping-risk": ["以 100% 比例查看文本框最后一行。", "加高文本框、精简文字，或安全地调整字号。", "另存交付副本，再运行一次 PPTLint。"],
    "readability.font-portability-risk": ["确认收件人的电脑是否安装了该字体。", "改用通用字体，或在许可允许时嵌入字体。", "换一台电脑打开交付副本，再运行一次 PPTLint。"],
    "readability.small-font": ["按会议室实际观看距离查看这一页。", "放大字号，或减少页面文字。", "再运行一次 PPTLint，并查看页面预览。"],
    "readability.low-contrast": ["查看高亮文字与实际背景的对比。", "加深文字、提亮背景，或增加纯色底。", "再运行一次 PPTLint，并查看页面预览。"],
    "editability.full-slide-image": ["确认对方是否需要修改这一页的文字、数字、图表或形状。", "把需要修改的内容重建为 PowerPoint 原生对象。", "再运行一次 PPTLint，确认整页图片数量。"],
}


@dataclass(frozen=True)
class ReadinessResult:
    status: str
    reasons: list[dict[str, object]]
    priority_actions: list[dict[str, object]]


def classify_finding(finding: Finding, *, language: str = "en") -> dict[str, object]:
    if finding.confidence != "high":
        disposition = "advisory"
    elif finding.rule_id in BLOCKER_RULES:
        disposition = "blocker"
    else:
        disposition = "review"
    impact = RULE_IMPACTS.get(
        finding.rule_id,
        "This issue may reduce delivery quality or requires a human decision before sharing.",
    )
    steps = RULE_FIX_STEPS.get(
        finding.rule_id,
        [
            finding.remediation,
            "Save changes to a separate delivery copy.",
            "Run PPTLint again and confirm that the reported item no longer appears.",
        ],
    )
    if language == "zh-CN":
        impact = ZH_IMPACTS.get(finding.rule_id, "这个问题可能影响外发效果，发送前需要人工确认。")
        steps = ZH_FIX_STEPS.get(
            finding.rule_id,
            [finding.remediation, "把修改另存为交付副本。", "再运行一次 PPTLint，确认该提醒已经处理。"],
        )
    return {"disposition": disposition, "impact": impact, "fixSteps": steps}


def assess_readiness(
    findings: list[Finding], *, renderer_status: str, language: str = "en"
) -> ReadinessResult:
    enriched = [(finding, classify_finding(finding, language=language)) for finding in findings]
    blockers = [(finding, detail) for finding, detail in enriched if detail["disposition"] == "blocker"]
    reviews = [(finding, detail) for finding, detail in enriched if detail["disposition"] == "review"]
    if blockers:
        status = "blocked"
        deciding = blockers
    elif reviews or renderer_status == "degraded":
        status = "review"
        deciding = reviews
    else:
        status = "ready"
        deciding = []

    reasons = [
        {
            "ruleId": finding.rule_id,
            "slideIndex": finding.slide_index,
            "evidence": finding.evidence,
            "impact": detail["impact"],
        }
        for finding, detail in deciding
    ]
    if renderer_status == "degraded" and not blockers:
        reasons.append(
            {
                "ruleId": "runtime.rendering-degraded",
                "slideIndex": None,
                "evidence": "A real LibreOffice preview was unavailable; structural wireframes were used.",
                "impact": (
                    "未能使用真实渲染器生成预览，部分视觉风险仍需人工查看。"
                    if language == "zh-CN"
                    else "Visual delivery risks could not be verified with a real renderer."
                ),
            }
        )

    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    disposition_rank = {"blocker": 3, "review": 2, "advisory": 1}
    ordered = sorted(
        enriched,
        key=lambda item: (
            -disposition_rank[str(item[1]["disposition"])],
            -severity_rank[item[0].severity],
            item[0].slide_index or 0,
            item[0].rule_id,
        ),
    )
    actions = [
        {
            "ruleId": finding.rule_id,
            "slideIndex": finding.slide_index,
            "disposition": detail["disposition"],
            "impact": detail["impact"],
            "fixSteps": detail["fixSteps"],
        }
        for finding, detail in ordered[:3]
    ]
    return ReadinessResult(status=status, reasons=reasons, priority_actions=actions)
