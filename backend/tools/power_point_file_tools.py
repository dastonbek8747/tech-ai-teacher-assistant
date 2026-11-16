from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from langchain_core.tools import tool
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

WORKSPACE = Path(
    os.getenv("PPTX_WORKSPACE", str(Path.cwd() / "presentations"))
).expanduser().resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _ok(**kwargs: Any) -> str:
    return _json({"success": True, **kwargs})


def _error(message: str) -> str:
    return _json({"success": False, "error": message})


def _safe_path(path_text: str, *, must_exist: bool = False,
               suffix: Optional[str] = ".pptx") -> Path:
    """Resolve a path and prevent access outside the configured workspace."""
    if not path_text or not path_text.strip():
        raise ValueError("Fayl yo'li bo'sh bo'lishi mumkin emas.")

    raw = Path(path_text).expanduser()
    path = (raw if raw.is_absolute() else WORKSPACE / raw).resolve()

    try:
        path.relative_to(WORKSPACE)
    except ValueError:
        raise ValueError(f"Faqat workspace ichidagi fayllarga ruxsat bor: {WORKSPACE}")

    if suffix and path.suffix.lower() != suffix:
        raise ValueError(f"Fayl kengaytmasi {suffix} bo'lishi kerak.")

    if must_exist and not path.is_file():
        raise FileNotFoundError(f"Fayl topilmadi: {path}")

    if not must_exist:
        path.parent.mkdir(parents=True, exist_ok=True)

    return path


def _load(path_text: str) -> tuple[Path, Presentation]:
    path = _safe_path(path_text, must_exist=True, suffix=".pptx")
    try:
        return path, Presentation(str(path))
    except Exception as exc:
        raise ValueError(
            "PPTX ochilmadi. Fayl buzilgan, himoyalangan yoki haqiqiy .pptx bo'lmasligi mumkin."
        ) from exc


def _save(prs: Presentation, output_path: str) -> Path:
    path = _safe_path(output_path, must_exist=False, suffix=".pptx")
    prs.save(str(path))
    return path


def _slide_index(prs: Presentation, slide_number: int) -> int:
    """Public tool slide numbers are 1-based."""
    if slide_number < 1 or slide_number > len(prs.slides):
        raise ValueError(
            f"Slayd raqami 1 dan {len(prs.slides)} gacha bo'lishi kerak."
        )
    return slide_number - 1


def _find_shape(slide: Any, shape_index: int) -> Any:
    """Shape indices are 0-based, matching the order returned by python-pptx."""
    if shape_index < 0 or shape_index >= len(slide.shapes):
        raise ValueError(
            f"Shape index 0 dan {len(slide.shapes) - 1} gacha bo'lishi kerak."
        )
    return slide.shapes[shape_index]


def _replace_paragraph_text(paragraph: Any, old: str, new: str) -> bool:
    """Replace text within runs where possible, retaining most run formatting."""
    if not old or old not in paragraph.text:
        return False

    # Simple and reliable when the match is fully inside one run.
    for run in paragraph.runs:
        if old in run.text:
            run.text = run.text.replace(old, new)
            return True

    # Cross-run match: rebuild the paragraph as a single run.
    replaced = paragraph.text.replace(old, new)
    paragraph.clear()
    paragraph.add_run().text = replaced
    return True


@tool
def list_presentations() -> str:
    """List all .pptx presentation files inside the configured PowerPoint workspace."""
    try:
        files = [
            {"name": p.name, "path": str(p.relative_to(WORKSPACE)),
             "size_bytes": p.stat().st_size}
            for p in WORKSPACE.rglob("*.pptx") if p.is_file()
        ]
        return _ok(workspace=str(WORKSPACE), files=files, count=len(files))
    except Exception as exc:
        return _error(str(exc))


@tool
def get_presentation_info(file_path: str) -> str:
    """Open a .pptx file and return its slide count, dimensions, and per-slide shape counts."""
    try:
        path, prs = _load(file_path)
        slides = []
        for i, slide in enumerate(prs.slides, start=1):
            slides.append({
                "slide_number": i,
                "shape_count": len(slide.shapes),
                "text_shape_count": sum(1 for s in slide.shapes if getattr(s, "has_text_frame", False)),
                "title": slide.shapes.title.text if slide.shapes.title else None,
            })
        return _ok(
            file_path=str(path.relative_to(WORKSPACE)),
            slide_count=len(prs.slides),
            width_inches=round(prs.slide_width / 914400, 2),
            height_inches=round(prs.slide_height / 914400, 2),
            slides=slides,
        )
    except Exception as exc:
        return _error(str(exc))


@tool
def read_slide_content(file_path: str, slide_number: int = 1) -> str:
    """Read text, tables, and shape metadata from one slide. Slide numbering starts at 1."""
    try:
        _, prs = _load(file_path)
        idx = _slide_index(prs, slide_number)
        slide = prs.slides[idx]
        shapes = []
        for i, shape in enumerate(slide.shapes):
            item = {
                "shape_index": i,
                "shape_name": shape.name,
                "shape_type": str(shape.shape_type),
                "text": shape.text if getattr(shape, "has_text_frame", False) else None,
            }
            if getattr(shape, "has_table", False):
                item["table"] = [
                    [cell.text for cell in row.cells]
                    for row in shape.table.rows
                ]
            shapes.append(item)
        return _ok(slide_number=slide_number, shapes=shapes)
    except Exception as exc:
        return _error(str(exc))


@tool
def read_all_slide_text(file_path: str) -> str:
    """Read all text from every slide in a .pptx file, including text inside tables."""
    try:
        _, prs = _load(file_path)
        result = []
        for number, slide in enumerate(prs.slides, start=1):
            shapes = []
            for i, shape in enumerate(slide.shapes):
                if getattr(shape, "has_text_frame", False) and shape.text.strip():
                    shapes.append({"shape_index": i, "text": shape.text})
                if getattr(shape, "has_table", False):
                    shapes.append({
                        "shape_index": i,
                        "table": [[c.text for c in row.cells] for row in shape.table.rows],
                    })
            result.append({
                "slide_number": number,
                "title": slide.shapes.title.text if slide.shapes.title else None,
                "content": shapes,
            })
        return _ok(slides=result)
    except Exception as exc:
        return _error(str(exc))


@tool
def search_presentation_text(file_path: str, query: str) -> str:
    """Search text in a presentation and return matching slide and shape indices."""
    try:
        _, prs = _load(file_path)
        q = query.casefold()
        matches = []
        for sn, slide in enumerate(prs.slides, start=1):
            for si, shape in enumerate(slide.shapes):
                texts = []
                if getattr(shape, "has_text_frame", False):
                    texts.append(shape.text)
                if getattr(shape, "has_table", False):
                    texts.extend(c.text for row in shape.table.rows for c in row.cells)
                text = "\n".join(texts)
                if q in text.casefold():
                    matches.append({
                        "slide_number": sn, "shape_index": si,
                        "matching_text": text[:1200],
                    })
        return _ok(query=query, matches=matches, count=len(matches))
    except Exception as exc:
        return _error(str(exc))


@tool
def create_presentation(output_path: str, title: str, subtitle: str = "") -> str:
    """Create a new presentation with a title slide and save it in the workspace."""
    try:
        path = _safe_path(output_path, must_exist=False, suffix=".pptx")
        if path.exists():
            return _error("Bu fayl allaqachon mavjud. Boshqa output_path tanlang.")
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = title
        if len(slide.placeholders) > 1:
            slide.placeholders[1].text = subtitle
        prs.save(str(path))
        return _ok(file_path=str(path.relative_to(WORKSPACE)), slide_count=1)
    except Exception as exc:
        return _error(str(exc))


@tool
def add_slide(file_path: str, output_path: str, title: str = "",
              body: str = "", layout: str = "title_content") -> str:
    """Add a slide. layout must be title_content, title_only, or blank. Saves to output_path."""
    try:
        _, prs = _load(file_path)
        layouts = {"title_content": 1, "title_only": 5, "blank": 6}
        if layout not in layouts:
            return _error("layout: title_content, title_only yoki blank bo'lishi kerak.")
        slide = prs.slides.add_slide(prs.slide_layouts[layouts[layout]])
        if slide.shapes.title and title:
            slide.shapes.title.text = title
        if layout == "title_content" and len(slide.placeholders) > 1 and body:
            slide.placeholders[1].text = body
        path = _save(prs, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   slide_number=len(prs.slides), layout=layout)
    except Exception as exc:
        return _error(str(exc))


@tool
def update_slide_text(file_path: str, output_path: str, slide_number: int,
                      shape_index: int, new_text: str) -> str:
    """Replace all text in a text shape identified by 1-based slide_number and 0-based shape_index."""
    try:
        _, prs = _load(file_path)
        slide = prs.slides[_slide_index(prs, slide_number)]
        shape = _find_shape(slide, shape_index)
        if not getattr(shape, "has_text_frame", False):
            return _error("Tanlangan shape matn maydoniga ega emas.")
        shape.text = new_text
        path = _save(prs, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   slide_number=slide_number, shape_index=shape_index)
    except Exception as exc:
        return _error(str(exc))


@tool
def replace_presentation_text(file_path: str, output_path: str,
                              old_text: str, new_text: str) -> str:
    """Replace text throughout a presentation, including table cells, and save to output_path."""
    try:
        if not old_text:
            return _error("old_text bo'sh bo'lishi mumkin emas.")
        _, prs = _load(file_path)
        count = 0
        for slide in prs.slides:
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    for paragraph in shape.text_frame.paragraphs:
                        if _replace_paragraph_text(paragraph, old_text, new_text):
                            count += 1
                if getattr(shape, "has_table", False):
                    for row in shape.table.rows:
                        for cell in row.cells:
                            if old_text in cell.text:
                                cell.text = cell.text.replace(old_text, new_text)
                                count += 1
        path = _save(prs, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)), replacements=count)
    except Exception as exc:
        return _error(str(exc))


@tool
def delete_slide(file_path: str, output_path: str, slide_number: int) -> str:
    """Delete a slide by its 1-based number and save to output_path. At least one slide must remain."""
    try:
        _, prs = _load(file_path)
        idx = _slide_index(prs, slide_number)
        if len(prs.slides) <= 1:
            return _error("Oxirgi slaydni o'chirib bo'lmaydi.")
        slide_id = prs.slides._sldIdLst[idx]
        prs.part.drop_rel(slide_id.rId)
        prs.slides._sldIdLst.remove(slide_id)
        path = _save(prs, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   deleted_slide=slide_number, remaining_slides=len(prs.slides))
    except Exception as exc:
        return _error(str(exc))


@tool
def reorder_slides(file_path: str, output_path: str, order_json: str) -> str:
    """Reorder slides using JSON list of all current slide numbers, e.g. '[3,1,2]'."""
    try:
        _, prs = _load(file_path)
        order = json.loads(order_json)
        n = len(prs.slides)
        if not isinstance(order, list) or sorted(order) != list(range(1, n + 1)):
            return _error(f"order_json barcha slayd raqamlarini bir martadan o'z ichiga olishi kerak: 1..{n}")
        slide_ids = list(prs.slides._sldIdLst)
        new_ids = [slide_ids[i - 1] for i in order]
        sld_id_list = prs.slides._sldIdLst
        for element in list(sld_id_list):
            sld_id_list.remove(element)
        for element in new_ids:
            sld_id_list.append(element)
        path = _save(prs, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)), order=order)
    except Exception as exc:
        return _error(str(exc))


@tool
def add_image(file_path: str, output_path: str, slide_number: int,
              image_path: str, left_inches: float, top_inches: float,
              width_inches: float = 3.0, height_inches: float = 0.0) -> str:
    """Add a workspace image to a slide. Set height_inches=0 to preserve image aspect ratio."""
    try:
        _, prs = _load(file_path)
        slide = prs.slides[_slide_index(prs, slide_number)]
        img = _safe_path(image_path, must_exist=True, suffix=None)
        if img.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"}:
            return _error("Rasm formati png, jpg, jpeg, gif, bmp yoki tiff bo'lishi kerak.")
        kwargs = {"width": Inches(width_inches)}
        if height_inches > 0:
            kwargs["height"] = Inches(height_inches)
        picture = slide.shapes.add_picture(
            str(img), Inches(left_inches), Inches(top_inches), **kwargs
        )
        path = _save(prs, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   slide_number=slide_number, picture_name=picture.name)
    except Exception as exc:
        return _error(str(exc))


@tool
def add_table(file_path: str, output_path: str, slide_number: int,
              table_data_json: str, left_inches: float = 0.5,
              top_inches: float = 1.5, width_inches: float = 9.0,
              height_inches: float = 3.0) -> str:
    """Add a table from JSON 2D array, e.g. '[[\"Name\",\"Score\"],[\"Ali\",\"95\"]]'."""
    try:
        data = json.loads(table_data_json)
        if not isinstance(data, list) or not data or not all(isinstance(r, list) for r in data):
            return _error("table_data_json 2D JSON array bo'lishi kerak.")
        cols = max(len(row) for row in data)
        if cols == 0:
            return _error("Jadvalda kamida bitta ustun bo'lishi kerak.")
        _, prs = _load(file_path)
        slide = prs.slides[_slide_index(prs, slide_number)]
        table = slide.shapes.add_table(
            len(data), cols, Inches(left_inches), Inches(top_inches),
            Inches(width_inches), Inches(height_inches)
        ).table
        for r, row in enumerate(data):
            for c in range(cols):
                table.cell(r, c).text = str(row[c]) if c < len(row) else ""
        path = _save(prs, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   slide_number=slide_number, rows=len(data), columns=cols)
    except Exception as exc:
        return _error(str(exc))


@tool
def set_slide_background(file_path: str, output_path: str, slide_number: int,
                         color_hex: str) -> str:
    """Set a slide background to a six-digit hex color such as '#17365D'."""
    try:
        color = color_hex.strip().lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            return _error("color_hex 6 ta hex raqamdan iborat bo'lishi kerak, masalan #17365D.")
        rgb = RGBColor.from_string(color.upper())
        _, prs = _load(file_path)
        slide = prs.slides[_slide_index(prs, slide_number)]
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = rgb
        path = _save(prs, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   slide_number=slide_number, background="#" + color.upper())
    except Exception as exc:
        return _error(str(exc))


@tool
def set_text_style(file_path: str, output_path: str, slide_number: int,
                   shape_index: int, font_size: int = 24,
                   font_name: str = "Arial", color_hex: str = "#222222",
                   bold: bool = False, alignment: str = "left") -> str:
    """Style all text in a shape. Alignment must be left, center, right, or justify."""
    try:
        color = color_hex.strip().lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            return _error("color_hex noto'g'ri. Masalan #222222.")
        alignments = {
            "left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER,
            "right": PP_ALIGN.RIGHT, "justify": PP_ALIGN.JUSTIFY,
        }
        if alignment not in alignments:
            return _error("alignment: left, center, right yoki justify bo'lishi kerak.")
        if font_size < 1 or font_size > 200:
            return _error("font_size 1 dan 200 gacha bo'lishi kerak.")
        _, prs = _load(file_path)
        slide = prs.slides[_slide_index(prs, slide_number)]
        shape = _find_shape(slide, shape_index)
        if not getattr(shape, "has_text_frame", False):
            return _error("Tanlangan shape matn maydoniga ega emas.")
        for paragraph in shape.text_frame.paragraphs:
            paragraph.alignment = alignments[alignment]
            for run in paragraph.runs:
                run.font.name = font_name
                run.font.size = Pt(font_size)
                run.font.bold = bold
                run.font.color.rgb = RGBColor.from_string(color.upper())
        path = _save(prs, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   slide_number=slide_number, shape_index=shape_index,
                   font_size=font_size, font_name=font_name,
                   color="#" + color.upper(), bold=bold, alignment=alignment)
    except Exception as exc:
        return _error(str(exc))


@tool
def update_table_cell(file_path: str, output_path: str, slide_number: int,
                      shape_index: int, row_index: int, column_index: int,
                      new_text: str) -> str:
    """Update one table cell using 0-based shape, row, and column indices."""
    try:
        _, prs = _load(file_path)
        slide = prs.slides[_slide_index(prs, slide_number)]
        shape = _find_shape(slide, shape_index)
        if not getattr(shape, "has_table", False):
            return _error("Tanlangan shape jadval emas.")
        table = shape.table
        if row_index < 0 or row_index >= len(table.rows):
            return _error("row_index jadval chegarasidan tashqarida.")
        if column_index < 0 or column_index >= len(table.columns):
            return _error("column_index jadval chegarasidan tashqarida.")
        table.cell(row_index, column_index).text = new_text
        path = _save(prs, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   slide_number=slide_number, row_index=row_index,
                   column_index=column_index)
    except Exception as exc:
        return _error(str(exc))


@tool
def save_presentation_copy(file_path: str, output_path: str) -> str:
    """Validate and save a copy of a .pptx presentation to another workspace path."""
    try:
        _, prs = _load(file_path)
        path = _save(prs, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   slide_count=len(prs.slides))
    except Exception as exc:
        return _error(str(exc))


POWERPOINT_TOOLS = [
    list_presentations,
    get_presentation_info,
    read_slide_content,
    read_all_slide_text,
    search_presentation_text,
    create_presentation,
    add_slide,
    update_slide_text,
    replace_presentation_text,
    delete_slide,
    reorder_slides,
    add_image,
    add_table,
    set_slide_background,
    set_text_style,
    update_table_cell,
    save_presentation_copy,
]
