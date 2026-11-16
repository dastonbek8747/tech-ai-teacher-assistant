"""
Word Management Toolkit for LangChain agents.

Install:
    pip install python-docx langchain-core

Optional environment variable:
    WORD_WORKSPACE=C:/path/to/your/document_workspace

Scope:
    - Supports .docx documents (not legacy .doc).
    - Restricts document and image paths to WORD_WORKSPACE.
    - Tools return JSON strings suitable for LangChain agents.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from langchain_core.tools import tool

WORKSPACE = Path(
    os.getenv("WORD_WORKSPACE", str(Path.cwd() / "documents"))
).expanduser().resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _ok(**kwargs: Any) -> str:
    return _json({"success": True, **kwargs})


def _error(message: str) -> str:
    return _json({"success": False, "error": message})


def _safe_path(path_text: str, *, must_exist: bool = False,
               suffix: Optional[str] = ".docx") -> Path:
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


def _load(path_text: str) -> tuple[Path, Document]:
    path = _safe_path(path_text, must_exist=True, suffix=".docx")
    try:
        return path, Document(str(path))
    except Exception as exc:
        raise ValueError(
            "DOCX ochilmadi. Fayl buzilgan, himoyalangan yoki haqiqiy .docx bo'lmasligi mumkin."
        ) from exc


def _save(doc: Document, output_path: str) -> Path:
    path = _safe_path(output_path, must_exist=False, suffix=".docx")
    doc.save(str(path))
    return path


def _all_paragraphs(doc: Document):
    """Yield paragraphs from document body and tables (including nested tables)."""
    for paragraph in doc.paragraphs:
        yield paragraph
    for table in doc.tables:
        yield from _table_paragraphs(table)
    for section in doc.sections:
        for part in (section.header, section.footer, section.first_page_header,
                     section.first_page_footer, section.even_page_header,
                     section.even_page_footer):
            for paragraph in part.paragraphs:
                yield paragraph
            for table in part.tables:
                yield from _table_paragraphs(table)


def _table_paragraphs(table):
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                yield paragraph
            for nested in cell.tables:
                yield from _table_paragraphs(nested)


def _paragraph_text(paragraph) -> str:
    return paragraph.text or ""


def _replace_paragraph_text(paragraph, old_text: str, new_text: str) -> bool:
    if old_text not in paragraph.text:
        return False
    # Preserve run formatting for matches fully contained in a single run.
    for run in paragraph.runs:
        if old_text in run.text:
            run.text = run.text.replace(old_text, new_text)
            return True
    # If the match spans runs, rebuild paragraph text; this can simplify formatting.
    updated = paragraph.text.replace(old_text, new_text)
    paragraph.clear()
    paragraph.add_run(updated)
    return True


def _set_cell_shading(cell, fill_hex: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill_hex.upper())


def _set_cell_text_color(cell, color_hex: str):
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.font.color.rgb = RGBColor.from_string(color_hex.upper())


@tool
def list_documents() -> str:
    """List all .docx files inside the configured Word workspace."""
    try:
        files = [
            {"name": p.name, "path": str(p.relative_to(WORKSPACE)),
             "size_bytes": p.stat().st_size}
            for p in WORKSPACE.rglob("*.docx") if p.is_file()
        ]
        return _ok(workspace=str(WORKSPACE), files=files, count=len(files))
    except Exception as exc:
        return _error(str(exc))


@tool
def get_document_info(file_path: str) -> str:
    """Get DOCX metadata such as paragraph, table, section, and word counts."""
    try:
        path, doc = _load(file_path)
        text = "\n".join(p.text for p in _all_paragraphs(doc))
        return _ok(
            file_path=str(path.relative_to(WORKSPACE)),
            paragraph_count=len(doc.paragraphs),
            table_count=len(doc.tables),
            section_count=len(doc.sections),
            word_count=len(re.findall(r"\S+", text)),
            character_count=len(text),
            headings=[
                {"index": i, "text": p.text, "style": p.style.name}
                for i, p in enumerate(doc.paragraphs)
                if p.text.strip() and p.style.name.lower().startswith("heading")
            ],
        )
    except Exception as exc:
        return _error(str(exc))


@tool
def read_document(file_path: str, include_tables: bool = True) -> str:
    """Read document paragraphs in order and optionally include table contents."""
    try:
        path, doc = _load(file_path)
        items = []
        for i, paragraph in enumerate(doc.paragraphs):
            items.append({
                "type": "paragraph", "index": i,
                "style": paragraph.style.name, "text": paragraph.text,
            })
        if include_tables:
            for ti, table in enumerate(doc.tables):
                items.append({
                    "type": "table", "table_index": ti,
                    "rows": [[cell.text for cell in row.cells] for row in table.rows],
                })
        return _ok(file_path=str(path.relative_to(WORKSPACE)), content=items)
    except Exception as exc:
        return _error(str(exc))


@tool
def search_document_text(file_path: str, query: str) -> str:
    """Search a DOCX document, including tables, headers, and footers."""
    try:
        _, doc = _load(file_path)
        if not query:
            return _error("query bo'sh bo'lishi mumkin emas.")
        matches = []
        for i, paragraph in enumerate(_all_paragraphs(doc)):
            if query.casefold() in paragraph.text.casefold():
                matches.append({"paragraph_index": i, "text": paragraph.text[:1500]})
        return _ok(query=query, matches=matches, count=len(matches))
    except Exception as exc:
        return _error(str(exc))


@tool
def create_document(output_path: str, title: str, content: str = "",
                   heading_style: str = "Title") -> str:
    """Create a new DOCX with a title and optional body content; paragraphs split on newlines."""
    try:
        path = _safe_path(output_path, must_exist=False, suffix=".docx")
        if path.exists():
            return _error("Bu fayl allaqachon mavjud. Boshqa output_path tanlang.")
        doc = Document()
        doc.add_paragraph(title, style=heading_style)
        for line in content.splitlines():
            doc.add_paragraph(line)
        doc.save(str(path))
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   paragraph_count=len(doc.paragraphs))
    except Exception as exc:
        return _error(str(exc))


@tool
def append_paragraph(file_path: str, output_path: str, text: str,
                     style: str = "Normal") -> str:
    """Append a paragraph to the end of a DOCX and save as output_path."""
    try:
        _, doc = _load(file_path)
        doc.add_paragraph(text, style=style)
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   paragraph_count=len(doc.paragraphs))
    except Exception as exc:
        return _error(str(exc))


@tool
def insert_paragraph(file_path: str, output_path: str, paragraph_index: int,
                     text: str, style: str = "Normal") -> str:
    """Insert a paragraph before the specified 0-based body paragraph index."""
    try:
        _, doc = _load(file_path)
        if paragraph_index < 0 or paragraph_index >= len(doc.paragraphs):
            return _error(f"paragraph_index 0 dan {len(doc.paragraphs)-1} gacha bo'lishi kerak.")
        anchor = doc.paragraphs[paragraph_index]
        new_p = OxmlElement("w:p")
        anchor._p.addprevious(new_p)
        from docx.text.paragraph import Paragraph
        paragraph = Paragraph(new_p, anchor._parent)
        paragraph.style = style
        paragraph.add_run(text)
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   inserted_before=paragraph_index)
    except Exception as exc:
        return _error(str(exc))


@tool
def update_paragraph(file_path: str, output_path: str, paragraph_index: int,
                     new_text: str) -> str:
    """Replace the entire text of a 0-based body paragraph, preserving paragraph style."""
    try:
        _, doc = _load(file_path)
        if paragraph_index < 0 or paragraph_index >= len(doc.paragraphs):
            return _error(f"paragraph_index 0 dan {len(doc.paragraphs)-1} gacha bo'lishi kerak.")
        paragraph = doc.paragraphs[paragraph_index]
        paragraph.clear()
        paragraph.add_run(new_text)
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   paragraph_index=paragraph_index)
    except Exception as exc:
        return _error(str(exc))


@tool
def replace_document_text(file_path: str, output_path: str,
                          old_text: str, new_text: str) -> str:
    """Replace matching text across document paragraphs, tables, headers, and footers."""
    try:
        if not old_text:
            return _error("old_text bo'sh bo'lishi mumkin emas.")
        _, doc = _load(file_path)
        replacements = 0
        # Deduplicate paragraph objects that may appear through merged table cells.
        seen = set()
        for paragraph in _all_paragraphs(doc):
            ident = id(paragraph._p)
            if ident in seen:
                continue
            seen.add(ident)
            if _replace_paragraph_text(paragraph, old_text, new_text):
                replacements += 1
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   replacements=replacements)
    except Exception as exc:
        return _error(str(exc))


@tool
def delete_paragraph(file_path: str, output_path: str,
                     paragraph_index: int) -> str:
    """Delete a 0-based body paragraph from the document."""
    try:
        _, doc = _load(file_path)
        if paragraph_index < 0 or paragraph_index >= len(doc.paragraphs):
            return _error(f"paragraph_index 0 dan {len(doc.paragraphs)-1} gacha bo'lishi kerak.")
        paragraph = doc.paragraphs[paragraph_index]
        element = paragraph._element
        element.getparent().remove(element)
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   deleted_paragraph=paragraph_index)
    except Exception as exc:
        return _error(str(exc))


@tool
def add_table(file_path: str, output_path: str,
              table_data_json: str, style: str = "Table Grid") -> str:
    """Append a table from a JSON 2D array, e.g. '[[\"Name\",\"Score\"],[\"Ali\",\"95\"]]'."""
    try:
        data = json.loads(table_data_json)
        if not isinstance(data, list) or not data or not all(isinstance(row, list) for row in data):
            return _error("table_data_json 2D JSON array bo'lishi kerak.")
        cols = max((len(row) for row in data), default=0)
        if cols == 0:
            return _error("Jadvalda kamida bitta ustun bo'lishi kerak.")
        _, doc = _load(file_path)
        table = doc.add_table(rows=len(data), cols=cols)
        try:
            table.style = style
        except KeyError:
            return _error(f"Jadval uslubi topilmadi: {style}")
        for r, row in enumerate(data):
            for c in range(cols):
                table.cell(r, c).text = str(row[c]) if c < len(row) else ""
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   table_index=len(doc.tables)-1, rows=len(data), columns=cols)
    except Exception as exc:
        return _error(str(exc))


@tool
def update_table_cell(file_path: str, output_path: str, table_index: int,
                      row_index: int, column_index: int, new_text: str) -> str:
    """Update a cell using 0-based table, row, and column indices."""
    try:
        _, doc = _load(file_path)
        if table_index < 0 or table_index >= len(doc.tables):
            return _error(f"table_index 0 dan {len(doc.tables)-1} gacha bo'lishi kerak.")
        table = doc.tables[table_index]
        if row_index < 0 or row_index >= len(table.rows):
            return _error("row_index jadval chegarasidan tashqarida.")
        if column_index < 0 or column_index >= len(table.columns):
            return _error("column_index jadval chegarasidan tashqarida.")
        table.cell(row_index, column_index).text = new_text
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   table_index=table_index, row_index=row_index,
                   column_index=column_index)
    except Exception as exc:
        return _error(str(exc))


@tool
def set_paragraph_style(file_path: str, output_path: str,
                        paragraph_index: int, style: str) -> str:
    """Set a body paragraph's named Word style, such as Normal, Title, Heading 1, or Subtitle."""
    try:
        _, doc = _load(file_path)
        if paragraph_index < 0 or paragraph_index >= len(doc.paragraphs):
            return _error(f"paragraph_index 0 dan {len(doc.paragraphs)-1} gacha bo'lishi kerak.")
        doc.paragraphs[paragraph_index].style = style
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   paragraph_index=paragraph_index, style=style)
    except Exception as exc:
        return _error(str(exc))


@tool
def set_paragraph_alignment(file_path: str, output_path: str,
                            paragraph_index: int, alignment: str) -> str:
    """Set paragraph alignment: left, center, right, or justify."""
    try:
        alignments = {
            "left": WD_ALIGN_PARAGRAPH.LEFT,
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
            "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
        }
        if alignment not in alignments:
            return _error("alignment: left, center, right yoki justify bo'lishi kerak.")
        _, doc = _load(file_path)
        if paragraph_index < 0 or paragraph_index >= len(doc.paragraphs):
            return _error(f"paragraph_index 0 dan {len(doc.paragraphs)-1} gacha bo'lishi kerak.")
        doc.paragraphs[paragraph_index].alignment = alignments[alignment]
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   paragraph_index=paragraph_index, alignment=alignment)
    except Exception as exc:
        return _error(str(exc))


@tool
def set_run_format(file_path: str, output_path: str, paragraph_index: int,
                   run_index: int, font_name: str = "Arial",
                   font_size: int = 12, color_hex: str = "#222222",
                   bold: bool = False, italic: bool = False,
                   underline: bool = False) -> str:
    """Format one run in a body paragraph using 0-based paragraph and run indices."""
    try:
        color = color_hex.strip().lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            return _error("color_hex 6 ta hex raqam bo'lishi kerak, masalan #222222.")
        if not 1 <= font_size <= 200:
            return _error("font_size 1 dan 200 gacha bo'lishi kerak.")
        _, doc = _load(file_path)
        if paragraph_index < 0 or paragraph_index >= len(doc.paragraphs):
            return _error("paragraph_index hujjat chegarasidan tashqarida.")
        paragraph = doc.paragraphs[paragraph_index]
        if run_index < 0 or run_index >= len(paragraph.runs):
            return _error(f"run_index 0 dan {len(paragraph.runs)-1} gacha bo'lishi kerak.")
        run = paragraph.runs[run_index]
        run.font.name = font_name
        run.font.size = Pt(font_size)
        run.font.color.rgb = RGBColor.from_string(color.upper())
        run.bold = bold
        run.italic = italic
        run.underline = underline
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   paragraph_index=paragraph_index, run_index=run_index,
                   font_name=font_name, font_size=font_size,
                   color="#" + color.upper(), bold=bold,
                   italic=italic, underline=underline)
    except Exception as exc:
        return _error(str(exc))


@tool
def add_image(file_path: str, output_path: str, image_path: str,
              width_inches: float = 4.0) -> str:
    """Append an image from the workspace to the end of a DOCX."""
    try:
        _, doc = _load(file_path)
        image = _safe_path(image_path, must_exist=True, suffix=None)
        if image.suffix.lower() not in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"}:
            return _error("Rasm formati png, jpg, jpeg, gif, bmp yoki tiff bo'lishi kerak.")
        if width_inches <= 0 or width_inches > 20:
            return _error("width_inches 0 dan katta va 20 dan kichik yoki teng bo'lishi kerak.")
        doc.add_picture(str(image), width=Inches(width_inches))
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   image_name=image.name, width_inches=width_inches)
    except Exception as exc:
        return _error(str(exc))


@tool
def set_document_margins(file_path: str, output_path: str,
                         top_inches: float = 1.0, bottom_inches: float = 1.0,
                         left_inches: float = 1.0, right_inches: float = 1.0) -> str:
    """Set page margins for every section in a DOCX."""
    try:
        values = [top_inches, bottom_inches, left_inches, right_inches]
        if any(v < 0 or v > 5 for v in values):
            return _error("Margin qiymatlari 0 dan 5 inch gacha bo'lishi kerak.")
        _, doc = _load(file_path)
        for section in doc.sections:
            section.top_margin = Inches(top_inches)
            section.bottom_margin = Inches(bottom_inches)
            section.left_margin = Inches(left_inches)
            section.right_margin = Inches(right_inches)
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   margins_inches={"top": top_inches, "bottom": bottom_inches,
                                   "left": left_inches, "right": right_inches})
    except Exception as exc:
        return _error(str(exc))


@tool
def save_document_copy(file_path: str, output_path: str) -> str:
    """Open, validate, and save a copy of a DOCX document to another workspace path."""
    try:
        _, doc = _load(file_path)
        path = _save(doc, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   paragraph_count=len(doc.paragraphs), table_count=len(doc.tables))
    except Exception as exc:
        return _error(str(exc))


WORD_TOOLS = [
    list_documents,
    get_document_info,
    read_document,
    search_document_text,
    create_document,
    append_paragraph,
    insert_paragraph,
    update_paragraph,
    replace_document_text,
    delete_paragraph,
    add_table,
    update_table_cell,
    set_paragraph_style,
    set_paragraph_alignment,
    set_run_format,
    add_image,
    set_document_margins,
    save_document_copy,
]


