"""PDF 报告生成

将 Markdown 报告转换为 PDF 格式。
优先使用 reportlab（已内置），回退到 weasyprint / pdfkit。

用法：
    from reportgen.pipeline.build_pdf import build_pdf_report
    success = build_pdf_report(md_content, "output/report.pdf", "output/assets")
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

def build_pdf_report(md_content: str, output_path: str, assets_dir: str = "") -> bool:
    """将 Markdown 报告转为 PDF。优先 reportlab，回退 weasyprint/pdfkit。"""
    if _try_reportlab(md_content, output_path, assets_dir):
        return True
    if _try_weasyprint(md_content, output_path, assets_dir):
        return True
    if _try_pdfkit(md_content, output_path, assets_dir):
        return True
    logger.warning("PDF 生成跳过：reportlab / weasyprint / pdfkit 均不可用")
    return False


# ─────────────────────────────────────────────
# reportlab 实现（核心）
# ─────────────────────────────────────────────

def _try_reportlab(md_content: str, output_path: str, assets_dir: str) -> bool:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, Image, Preformatted, KeepTogether,
        )
        from reportlab.platypus import ListFlowable, ListItem
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        logger.warning("reportlab 未安装")
        return False

    try:
        _register_chinese_fonts(pdfmetrics, TTFont)
        story = _md_to_story(
            md_content, assets_dir,
            A4=A4, Paragraph=Paragraph, Spacer=Spacer,
            Table=Table, TableStyle=TableStyle, colors=colors,
            HRFlowable=HRFlowable, Image=Image, Preformatted=Preformatted,
            KeepTogether=KeepTogether, ListFlowable=ListFlowable, ListItem=ListItem,
            cm=cm,
        )
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=2.5 * cm, rightMargin=2.5 * cm,
            topMargin=2.0 * cm, bottomMargin=2.0 * cm,
            title="仿真分析报告",
            author="SimuReport",
        )
        doc.build(story)
        logger.info(f"PDF 生成成功（reportlab）: {output_path}")
        return True
    except Exception as e:
        logger.error(f"reportlab PDF 生成失败: {e}", exc_info=True)
        return False


def _register_chinese_fonts(pdfmetrics, TTFont):
    """注册系统中文字体，按优先级尝试"""
    candidates = [
        ("SimSun",    r"C:\Windows\Fonts\simsun.ttc"),
        ("SimHei",    r"C:\Windows\Fonts\simhei.ttf"),
        ("MsYaHei",   r"C:\Windows\Fonts\msyh.ttc"),
        ("MsYaHeiB",  r"C:\Windows\Fonts\msyhbd.ttc"),
        ("FangSong",  r"C:\Windows\Fonts\simfang.ttf"),
    ]
    registered = []
    for name, path in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                registered.append(name)
            except Exception:
                pass
    return registered


def _get_rl_styles(cm):
    """构建全套 ParagraphStyle"""
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    # 选择已注册的中文字体
    _cn_fonts = ["MsYaHei", "SimHei", "SimSun", "FangSong", "Helvetica"]
    face = next(
        (f for f in _cn_fonts
         if f in __import__('reportlab.pdfbase.pdfmetrics', fromlist=['getRegisteredFontNames'])
         .getRegisteredFontNames()),
        "Helvetica"
    )
    face_b = next(
        (f for f in ["MsYaHeiB", "SimHei", face]
         if f in __import__('reportlab.pdfbase.pdfmetrics', fromlist=['getRegisteredFontNames'])
         .getRegisteredFontNames()),
        face
    )

    base = dict(fontName=face, fontSize=10.5, leading=18, textColor=colors.HexColor("#222222"))
    return {
        "h1": ParagraphStyle("h1", fontName=face_b, fontSize=18, leading=26,
                              spaceAfter=8, spaceBefore=16,
                              textColor=colors.HexColor("#111111"),
                              borderPad=(0, 0, 4, 0)),
        "h2": ParagraphStyle("h2", fontName=face_b, fontSize=14, leading=22,
                              spaceAfter=6, spaceBefore=12,
                              textColor=colors.HexColor("#1a1a2e")),
        "h3": ParagraphStyle("h3", fontName=face_b, fontSize=12, leading=20,
                              spaceAfter=4, spaceBefore=10,
                              textColor=colors.HexColor("#333333")),
        "body": ParagraphStyle("body", **base, spaceAfter=4, firstLineIndent=21),
        "list": ParagraphStyle("list", **base, spaceAfter=2, leftIndent=18, firstLineIndent=0),
        "code": ParagraphStyle("code", fontName="Courier", fontSize=9, leading=14,
                               backColor=colors.HexColor("#f5f5f5"),
                               textColor=colors.HexColor("#333333"),
                               spaceAfter=6, leftIndent=12, rightIndent=12),
        "caption": ParagraphStyle("caption", fontName=face, fontSize=9, leading=13,
                                  textColor=colors.HexColor("#666666"),
                                  alignment=TA_CENTER, spaceAfter=6),
    }


def _md_to_story(md_content, assets_dir, **rl):
    """将 Markdown 解析为 reportlab flowable 列表"""
    from reportlab.platypus import Spacer, HRFlowable

    story = []
    styles = _get_rl_styles(rl['cm'])
    assets_path = Path(assets_dir).resolve() if assets_dir else None

    lines = md_content.splitlines()
    i = 0
    in_code_block = False
    code_lines = []
    in_table = False
    table_rows = []
    table_header = []

    while i < len(lines):
        line = lines[i]

        # ── 代码块 ──────────────────────────────
        if line.startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_lines = []
                i += 1
                continue
            else:
                code_text = "\n".join(code_lines)
                story.append(rl['Preformatted'](code_text, styles["code"]))
                story.append(Spacer(1, 4))
                in_code_block = False
                code_lines = []
                i += 1
                continue
        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # ── 表格 ─────────────────────────────────
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not in_table:
                in_table = True
                table_header = cells
                table_rows = [cells]
            elif all(re.match(r"^[-:]+$", c) for c in cells if c):
                pass  # separator row
            else:
                table_rows.append(cells)
            i += 1
            continue
        elif in_table:
            story.append(_build_table(table_rows, rl))
            story.append(Spacer(1, 6))
            in_table = False
            table_rows = []
            table_header = []
            continue

        # ── 标题 ─────────────────────────────────
        h_match = re.match(r"^(#{1,3})\s+(.*)", line)
        if h_match:
            level = len(h_match.group(1))
            text = _escape_rl(h_match.group(2))
            key = f"h{min(level, 3)}"
            story.append(rl['Paragraph'](text, styles[key]))
            if level == 1:
                story.append(HRFlowable(width="100%", thickness=1,
                                        color=rl['colors'].HexColor("#dddddd"),
                                        spaceAfter=6))
            i += 1
            continue

        # ── 水平分隔线 ────────────────────────────
        if re.match(r"^---+$", line.strip()):
            story.append(HRFlowable(width="100%", thickness=0.5,
                                    color=rl['colors'].HexColor("#cccccc"),
                                    spaceBefore=4, spaceAfter=4))
            i += 1
            continue

        # ── 无序列表 ─────────────────────────────
        if re.match(r"^[\-\*\+]\s+", line):
            items = []
            while i < len(lines) and re.match(r"^[\-\*\+]\s+", lines[i]):
                text = _escape_rl(re.sub(r"^[\-\*\+]\s+", "", lines[i]))
                items.append(rl['ListItem'](rl['Paragraph']("• " + text, styles["list"])))
                i += 1
            story.append(rl['ListFlowable'](items, bulletType='bullet',
                                            leftIndent=18, bulletFontSize=0))
            continue

        # ── 有序列表 ─────────────────────────────
        if re.match(r"^\d+\.\s+", line):
            items = []
            n = 1
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                text = _escape_rl(re.sub(r"^\d+\.\s+", "", lines[i]))
                items.append(rl['ListItem'](rl['Paragraph'](text, styles["list"]),
                                            value=str(n)))
                n += 1
                i += 1
            story.append(rl['ListFlowable'](items, bulletType='1', leftIndent=18))
            continue

        # ── 图片 ─────────────────────────────────
        img_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)", line)
        if img_match and assets_path:
            alt = img_match.group(1)
            src = img_match.group(2)
            img_node = _build_image(src, alt, assets_path, rl, styles)
            if img_node:
                story.extend(img_node)
            i += 1
            continue

        # ── 空行 ─────────────────────────────────
        if not line.strip():
            story.append(Spacer(1, 6))
            i += 1
            continue

        # ── 普通段落 ─────────────────────────────
        text = _escape_rl(line)
        if text:
            story.append(rl['Paragraph'](text, styles["body"]))
        i += 1

    # 收尾：未关闭的表格
    if in_table and table_rows:
        story.append(_build_table(table_rows, rl))

    return story


def _build_table(rows, rl):
    """构建 reportlab Table flowable"""
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors as c

    if not rows:
        return rl['Spacer'](1, 0)

    from reportlab.lib.styles import ParagraphStyle
    cell_style = ParagraphStyle("tc", fontName="Helvetica", fontSize=9, leading=13)
    try:
        from reportlab.pdfbase.pdfmetrics import getRegisteredFontNames
        for fn in ["MsYaHei", "SimSun", "SimHei"]:
            if fn in getRegisteredFontNames():
                cell_style = ParagraphStyle("tc", fontName=fn, fontSize=9, leading=13)
                break
    except Exception:
        pass

    data = [[rl['Paragraph'](_escape_rl(cell), cell_style) for cell in row]
            for row in rows]

    col_count = max(len(r) for r in data)
    col_width = (16 * rl['cm']) / max(col_count, 1)

    t = Table(data, colWidths=[col_width] * col_count, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  c.HexColor("#e8eaf6")),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("GRID",        (0, 0), (-1, -1), 0.5, c.HexColor("#bbbbbb")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [c.HexColor("#ffffff"), c.HexColor("#f8f9fa")]),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN",      (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _build_image(src: str, alt: str, assets_path: Path, rl, styles) -> list:
    """尝试嵌入图片，返回 [Image, caption] 或 []"""
    from reportlab.platypus import Image as RLImage
    candidates = [
        assets_path / src,
        assets_path / Path(src).name,
        Path(src),
    ]
    for p in candidates:
        if p.exists():
            try:
                max_w = 14 * rl['cm']
                img = RLImage(str(p), width=max_w, kind='proportional')
                items = [img]
                if alt:
                    items.append(rl['Paragraph'](f"图：{alt}", styles["caption"]))
                return items
            except Exception:
                pass
    return []


def _escape_rl(text: str) -> str:
    """转义 reportlab Paragraph 特殊字符，同时保留简单的 bold/italic/code 标记"""
    # bold: **text** → <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # italic: *text* → <i>text</i>
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    # inline code: `code` → <font face="Courier" size="9">code</font>
    text = re.sub(r'`([^`]+)`', r'<font face="Courier" size="9">\1</font>', text)
    # escape & < > that are NOT part of tags we just created
    # (simple approach: protect our tags, then escape bare chars)
    # Since we just created well-formed tags, only need to escape stray & < >
    # outside of them – handled by reportlab's Paragraph parser itself for the
    # entity &amp; etc., so just ensure & is escaped when not already an entity
    text = re.sub(r'&(?!amp;|lt;|gt;|nbsp;|#)', '&amp;', text)
    return text


# ─────────────────────────────────────────────
# 回退策略
# ─────────────────────────────────────────────

def _md_to_html(md_content: str, assets_dir: str = "") -> str:
    import markdown
    html_body = markdown.markdown(md_content, extensions=["tables", "fenced_code", "toc"])
    if assets_dir:
        ap = Path(assets_dir).resolve()
        html_body = html_body.replace('src="assets/', f'src="file:///{ap}/')
        html_body = html_body.replace("src='assets/", f"src='file:///{ap}/")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{{font-family:SimSun,sans-serif;font-size:11pt;line-height:1.8}}
h1{{font-size:18pt}}h2{{font-size:14pt}}h3{{font-size:12pt}}
table{{border-collapse:collapse}}td,th{{border:1px solid #aaa;padding:4px 8px}}
</style></head><body>{html_body}</body></html>"""


def _try_weasyprint(md_content: str, output_path: str, assets_dir: str) -> bool:
    try:
        import markdown  # noqa
        from weasyprint import HTML
    except ImportError:
        return False
    try:
        HTML(string=_md_to_html(md_content, assets_dir)).write_pdf(output_path)
        logger.info(f"PDF 生成成功（weasyprint）: {output_path}")
        return True
    except Exception as e:
        logger.error(f"weasyprint 失败: {e}")
        return False


def _try_pdfkit(md_content: str, output_path: str, assets_dir: str) -> bool:
    try:
        import markdown  # noqa
        import pdfkit
    except ImportError:
        return False
    try:
        opts = {"encoding": "UTF-8", "page-size": "A4",
                "margin-top": "20mm", "margin-bottom": "20mm",
                "margin-left": "25mm", "margin-right": "25mm"}
        pdfkit.from_string(_md_to_html(md_content, assets_dir), output_path, options=opts)
        logger.info(f"PDF 生成成功（pdfkit）: {output_path}")
        return True
    except Exception as e:
        logger.error(f"pdfkit 失败: {e}")
        return False
