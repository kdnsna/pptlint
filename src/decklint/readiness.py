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
    "policy.notes-forbidden",
    "policy.hidden-slide-forbidden",
    "policy.external-link-forbidden",
    "policy.font-not-allowed",
    "policy.font-size-below-minimum",
    "policy.color-not-allowed",
    "policy.alt-text-required",
}

RULE_IMPACTS = {
    "integrity.broken-relationship": "PowerPoint may repair the file, omit content, or refuse to open it.",
    "integrity.empty-deck": "The file contains no slide that can be presented.",
    "integrity.missing-content-type": "PowerPoint may repair or omit the undeclared package part.",
    "integrity.notes-relationship": "Speaker notes may not behave consistently even when slides still render.",
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
    "integrity.large-package": "The file may be slow to send, open, or present on another computer.",
    "integrity.duplicate-media": "Repeated media increases file size without improving the presentation.",
    "readability.motion-portability-risk": "Animations or transitions may look different after export or in another app.",
    "editability.media-portability-risk": "Audio or video may fail when codecs, links, or apps change.",
    "policy.notes-forbidden": "The file violates the approved rule that delivery copies must not contain notes.",
    "policy.hidden-slide-forbidden": "The file violates the approved rule that delivery copies must not contain hidden slides.",
    "policy.external-link-forbidden": "The file violates the approved rule that delivery copies must not use external links.",
    "policy.font-not-allowed": "The slide uses a font outside the approved brand or delivery set.",
    "policy.font-size-below-minimum": "The slide uses text smaller than the approved minimum.",
    "policy.color-not-allowed": "The slide uses a color outside the approved brand palette.",
    "policy.alt-text-required": "The file does not meet the approved image-description requirement.",
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
    "integrity.notes-relationship": [
        "Open Notes view and confirm that notes still appear on the affected slides.",
        "Recreate the notes master or save a clean delivery copy when PowerPoint reports a repair.",
        "Run PPTLint again and confirm the notes relationship is valid.",
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
    "integrity.notes-relationship": "页面可能仍能放映，但讲者备注在其他电脑上可能工作不正常。",
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
    "integrity.large-package": "文件过大时，发送、打开和现场播放都可能变慢。",
    "integrity.duplicate-media": "同一媒体被重复保存，会让文件无意义地变大。",
    "readability.motion-portability-risk": "动画或转场在导出后、换软件后可能和原来不同。",
    "editability.media-portability-risk": "换电脑、编解码器或播放软件后，音视频可能无法播放。",
    "policy.notes-forbidden": "交付规则明确禁止备注，但文件中仍然保留了备注。",
    "policy.hidden-slide-forbidden": "交付规则明确禁止隐藏页，但文件中仍然存在隐藏页。",
    "policy.external-link-forbidden": "交付规则明确禁止外部链接，但文件中仍然存在外链。",
    "policy.font-not-allowed": "页面使用了品牌或交付规范之外的字体。",
    "policy.font-size-below-minimum": "页面文字小于交付规范允许的最小字号。",
    "policy.color-not-allowed": "页面使用了品牌规范之外的颜色。",
    "policy.alt-text-required": "图片没有满足交付规范要求的替代文字。",
}

ZH_FIX_STEPS = {
    "integrity.notes-relationship": ["打开备注视图，确认相关页面的备注仍然存在。", "如果 PowerPoint 提示修复，重建备注母版或另存干净副本。", "再运行一次 PPTLint，确认备注关系恢复正常。"],
    "privacy.comments": ["在 PowerPoint 的“审阅”中查看全部批注。", "删除不应外发的批注。", "另存交付副本，再运行一次 PPTLint。"],
    "privacy.external-relationship": ["在“文件 > 信息”中检查链接和外部内容。", "把内容嵌入文件、删除链接，或确认该链接可以外发。", "另存交付副本，再运行一次 PPTLint。"],
    "privacy.speaker-notes": ["打开报告所示页面的备注区。", "删除机密、草稿或只供内部使用的文字。", "再运行一次 PPTLint，确认提醒消失。"],
    "privacy.hidden-slide": ["在幻灯片浏览视图中查看全部隐藏页。", "删除不应外发的页面，或明确确认可以保留。", "另存交付副本，再运行一次 PPTLint。"],
    "privacy.personal-metadata": ["在“文件 > 信息”中查看文档属性。", "在交付副本中删除不需要的个人信息。", "再运行一次 PPTLint，确认提醒消失。"],
    "readability.off-canvas-text": ["在报告所示页面选中文本框，打开“形状格式 > 对齐”。", "先对齐到幻灯片，再把对象移入四周安全边距；不要只把字号缩小。", "以 100% 比例查看边缘并另存副本，再运行 PPTLint。"],
    "readability.text-overlap": ["在报告所示页面用 Shift 同时选中相互遮挡的对象。", "使用“形状格式 > 对齐 / 横向分布 / 纵向分布”统一边线和间距；空间不足时优先重排，不压缩文字。", "以 100% 比例检查遮挡和留白，另存副本后再运行 PPTLint。"],
    "readability.text-clipping-risk": ["以 100% 比例查看文本框最后一行，并打开“设置形状格式 > 文本选项 > 文本框”。", "关闭“溢出时缩排文字”，优先加高文本框、调整内边距或重排同页对象；保持整套正文最小字号。", "另存交付副本，再运行 PPTLint，确认末行完整。"],
    "readability.font-portability-risk": ["在“开始 > 替换 > 替换字体”中定位该字体，并确认目标电脑是否安装。", "替换为整套 PPT 已在使用的通用字体；必须保留时，在“文件 > 选项 > 保存”中按许可嵌入字体。", "在另一台电脑或目标软件中打开副本，再运行 PPTLint。"],
    "readability.small-font": ["切换到“视图 > 幻灯片浏览”，先确认这一页正文是否明显小于相邻页面。", "回到普通视图，统一正文层级并放大字号；空间不足时重排为两栏或减少装饰，不用自动缩排硬塞。", "按实际观看距离播放一遍，另存副本后再运行 PPTLint。"],
    "readability.low-contrast": ["选中高亮文字，打开“形状格式 > 文本填充”，确认它与实际背景的明暗关系。", "优先使用整套主题中的深色或浅色文字；图片背景复杂时增加低透明度纯色底，不用重阴影补救。", "进入放映模式并模拟较亮环境，另存副本后再运行 PPTLint。"],
    "editability.full-slide-image": ["确认接收方需要修改哪些文字、数字、图表或形状，并保留原图作为对照。", "用文本框、形状、表格或原生图表重建关键内容；原图只作为非文字视觉层，不能盖住可编辑对象。", "逐项双击确认可编辑，另存副本后再运行 PPTLint。"],
    "accessibility.missing-alt-text": ["确认图片是信息内容还是纯装饰。", "为信息图片添加简洁替代文字；装饰图片标记为装饰。", "再运行一次 PPTLint，确认提醒消失。"],
    "accessibility.missing-title": ["确认这一页的核心结论。", "使用标题占位符添加唯一且清楚的页面标题。", "再运行一次 PPTLint，确认页面可以被正确导航。"],
    "accessibility.reading-order-risk": ["在 PowerPoint 的选择窗格中查看对象顺序。", "按标题、正文、图表和辅助说明的阅读顺序重新排列。", "使用辅助阅读检查再次确认。"],
    "readability.dense-text": ["先写下观众看完这一页必须记住的唯一结论，并把它作为页面标题。", "不删原文时，使用标题、分组、两栏和留白建立层级；若仍无法达到最小字号，停止自动调整并请用户决定是否拆页。", "以幻灯片放映模式计时阅读，另存副本后再运行 PPTLint。"],
    "readability.blank-slide": ["确认空白页是否有意保留。", "删除意外空白页，或恢复缺失内容。", "再运行一次 PPTLint。"],
    "readability.unusual-aspect-ratio": ["确认最终屏幕、投影或打印尺寸。", "把交付副本调整为目标设备支持的页面比例。", "在实际设备上打开并再次检查。"],
    "consistency.font-outlier": ["在“开始 > 替换 > 替换字体”中确认异常字体的出现范围，并核对它是否承担刻意强调。", "非刻意使用时，替换为当前主题的标题或正文字体；不要逐个文本框手工改。", "切换到幻灯片浏览视图检查全套层级，再运行 PPTLint。"],
    "consistency.repeated-layout": ["在“视图 > 幻灯片浏览”中连续查看报告点名的页面，确认是否所有页面都在争夺同等注意力。", "保留主题字体和颜色，只改变信息结构：在图文分栏、数据重点、流程、对比或留白陈述中选择更匹配内容的一种。", "缩略图浏览整套 PPT，确认重点页能被一眼找到。"],
    "integrity.large-package": ["先另存一份交付副本。", "压缩过大的图片、音视频，并删除未使用的媒体。", "再运行一次 PPTLint，确认文件体积已经下降。"],
    "integrity.duplicate-media": ["确认重复媒体是否确实为同一份内容。", "在交付副本中复用同一资源或删除多余副本。", "再运行一次 PPTLint，确认重复媒体数量下降。"],
    "readability.motion-portability-risk": ["在最终使用的软件和设备上完整播放一次。", "把关键结论做成不依赖动画也能看懂的静态内容。", "另存交付副本，并再次检查。"],
    "editability.media-portability-risk": ["确认音视频已经嵌入，并能在目标电脑上播放。", "准备通用格式或可替代的静态页面。", "在断网环境和另一台电脑上试播。"],
    "policy.notes-forbidden": ["打开备注视图，检查全部页面。", "删除交付规范不允许保留的备注。", "另存交付副本，再按同一规范检查。"],
    "policy.hidden-slide-forbidden": ["在幻灯片浏览视图中找出隐藏页。", "删除隐藏页，或把确需交付的页面取消隐藏。", "另存交付副本，再按同一规范检查。"],
    "policy.external-link-forbidden": ["检查报告所示的外部网址或本地文件链接。", "把内容嵌入文件，或删除不允许的链接。", "另存交付副本，再按同一规范检查。"],
    "policy.font-not-allowed": ["确认报告所示字体是否在批准清单内。", "替换为品牌或交付规范允许的字体。", "再按同一规范检查，确认字体统一。"],
    "policy.font-size-below-minimum": ["查看报告所示文字在实际观看距离下是否清楚。", "放大字号、精简内容或拆成多页。", "再按同一规范检查，确认达到最小字号。"],
    "policy.color-not-allowed": ["确认报告所示颜色是否有业务含义。", "替换为品牌规范允许的颜色。", "再按同一规范检查，确认配色合规。"],
    "policy.alt-text-required": ["确认图片是信息内容还是纯装饰。", "为信息图片添加简洁替代文字；装饰图片标记为装饰。", "再按同一规范检查，确认图片说明完整。"],
}

ZH_MESSAGES = {
    "integrity.broken-relationship": "PPTX 中有关系指向缺失的文件对象。",
    "integrity.empty-deck": "文件中没有可演示的幻灯片。",
    "integrity.missing-content-type": "PPTX 中有对象缺少内容类型声明。",
    "integrity.notes-relationship": "讲者备注关系不完整。",
    "integrity.large-package": "文件体积较大，可能影响发送和打开。",
    "integrity.duplicate-media": "文件中包含重复媒体资源。",
    "privacy.comments": "文件中仍保留批注。",
    "privacy.external-relationship": "文件中包含外部网址或本地文件关系。",
    "privacy.speaker-notes": "页面中仍保留讲者备注。",
    "privacy.hidden-slide": "文件中仍保留隐藏页。",
    "privacy.personal-metadata": "文件中仍保留作者或编辑者信息。",
    "readability.off-canvas-text": "有文字超出幻灯片画布。",
    "readability.text-overlap": "页面中有文字区域可能互相遮挡。",
    "readability.text-clipping-risk": "文本框存在末行被截断的风险。",
    "readability.font-portability-risk": "所用字体在其他电脑上可能被替换。",
    "readability.small-font": "页面文字小于当前场景建议字号。",
    "readability.low-contrast": "文字与背景的对比度不足。",
    "readability.dense-text": "页面文字较密，现场可能来不及阅读。",
    "readability.blank-slide": "文件中存在可能非预期的空白页。",
    "readability.unusual-aspect-ratio": "页面比例不属于常见演示比例。",
    "readability.motion-portability-risk": "动画或转场在其他环境中可能发生变化。",
    "editability.full-slide-image": "页面主要由整页图片构成，关键内容难以编辑。",
    "editability.media-portability-risk": "音视频在其他电脑或软件中可能无法播放。",
    "accessibility.missing-alt-text": "图片缺少替代文字。",
    "accessibility.missing-title": "页面缺少可识别的标题。",
    "accessibility.reading-order-risk": "对象顺序可能不符合自然阅读顺序。",
    "consistency.font-outlier": "少量字体与整套演示文稿不一致。",
    "consistency.repeated-layout": "连续页面使用了相同的结构版式。",
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
    message = (
        ZH_MESSAGES.get(finding.rule_id, "发现一项需要在交付前确认的问题。")
        if language == "zh-CN"
        else finding.message
    )
    return {"disposition": disposition, "message": message, "impact": impact, "fixSteps": steps}


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
    actions: list[dict[str, object]] = []
    seen_rules: set[str] = set()
    for finding, detail in ordered:
        if finding.rule_id in seen_rules:
            continue
        seen_rules.add(finding.rule_id)
        related = [item for item, _ in enriched if item.rule_id == finding.rule_id]
        affected_slides = sorted(
            {item.slide_index for item in related if item.slide_index is not None}
        )
        actions.append(
            {
                "ruleId": finding.rule_id,
                "slideIndex": finding.slide_index,
                "affectedSlides": affected_slides,
                "findingCount": len(related),
                "disposition": detail["disposition"],
                "impact": detail["impact"],
                "fixSteps": detail["fixSteps"],
            }
        )
        if len(actions) == 3:
            break
    return ReadinessResult(status=status, reasons=reasons, priority_actions=actions)
