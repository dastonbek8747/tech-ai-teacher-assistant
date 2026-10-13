from __future__ import annotations
import json
import os
import re
from copy import copy
from pathlib import Path
from typing import Any, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from langchain_core.tools import tool

WORKSPACE = Path(
    os.getenv("EXCEL_WORKSPACE", str(Path.cwd() / "spreadsheets"))
).expanduser().resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)
SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm"}


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _ok(**kwargs: Any) -> str:
    return _json({"success": True, **kwargs})


def _error(message: str) -> str:
    return _json({"success": False, "error": message})


def _safe_path(path_text: str, *, must_exist: bool = False,
               suffix: Optional[str] = None) -> Path:
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
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("Faqat .xlsx yoki .xlsm fayllar qo'llab-quvvatlanadi.")
    if must_exist and not path.is_file():
        raise FileNotFoundError(f"Fayl topilmadi: {path}")
    if not must_exist:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load(path_text: str, data_only: bool = False):
    path = _safe_path(path_text, must_exist=True)
    keep_vba = path.suffix.lower() == ".xlsm"
    try:
        wb = load_workbook(
            str(path), data_only=data_only, keep_vba=keep_vba,
            read_only=False, keep_links=True
        )
        return path, wb
    except Exception as exc:
        raise ValueError(
            "Excel fayli ochilmadi. Fayl buzilgan, himoyalangan yoki qo'llab-quvvatlanmaydigan formatda bo'lishi mumkin."
        ) from exc


def _save(wb, output_path: str) -> Path:
    path = _safe_path(output_path, must_exist=False)
    if path.suffix.lower() == ".xlsm" and not getattr(wb, "vba_archive", None):
        # Saving a workbook as .xlsm without preserved VBA may be misleading.
        # It is still valid for macro-free workbooks, but warn via result.
        pass
    wb.save(str(path))
    return path


def _get_sheet(wb, sheet_name: str):
    if sheet_name not in wb.sheetnames:
        raise ValueError(
            f"'{sheet_name}' varaq topilmadi. Mavjud varaqlar: {', '.join(wb.sheetnames)}"
        )
    return wb[sheet_name]


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _cell_ref(row: int, column: int) -> str:
    return f"{get_column_letter(column)}{row}"


@tool
def list_workbooks() -> str:
    """List all .xlsx and .xlsm Excel workbooks in the configured workspace."""
    try:
        files = [
            {"name": p.name, "path": str(p.relative_to(WORKSPACE)),
             "size_bytes": p.stat().st_size, "format": p.suffix.lower()}
            for p in WORKSPACE.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        return _ok(workspace=str(WORKSPACE), files=files, count=len(files))
    except Exception as exc:
        return _error(str(exc))


@tool
def get_workbook_info(file_path: str) -> str:
    """Return workbook sheet names, dimensions, and non-empty cell counts."""
    try:
        path, wb = _load(file_path, data_only=False)
        sheets = []
        for ws in wb.worksheets:
            nonempty = sum(
                1 for row in ws.iter_rows()
                for cell in row if cell.value is not None
            )
            sheets.append({
                "sheet_name": ws.title,
                "max_row": ws.max_row,
                "max_column": ws.max_column,
                "dimensions": ws.calculate_dimension(),
                "non_empty_cells": nonempty,
                "freeze_panes": str(ws.freeze_panes) if ws.freeze_panes else None,
                "auto_filter": ws.auto_filter.ref or None,
                "merged_ranges": [str(r) for r in ws.merged_cells.ranges],
            })
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_names=wb.sheetnames, sheet_count=len(wb.sheetnames),
                   sheets=sheets)
    except Exception as exc:
        return _error(str(exc))


@tool
def read_sheet_range(file_path: str, sheet_name: str,
                     cell_range: str = "A1:Z30",
                     values_only: bool = True) -> str:
    """Read a bounded Excel cell range, e.g. A1:D20. Returns cell coordinates and values."""
    try:
        _, wb = _load(file_path, data_only=values_only)
        ws = _get_sheet(wb, sheet_name)
        if not re.fullmatch(r"\$?[A-Z]{1,3}\$?\d+:\$?[A-Z]{1,3}\$?\d+", cell_range.upper()):
            return _error("cell_range formati A1:D20 kabi bo'lishi kerak.")
        rows = []
        for row in ws[cell_range]:
            rows.append([
                {"cell": cell.coordinate, "value": _serialize(cell.value)}
                for cell in row
            ])
        return _ok(sheet_name=sheet_name, cell_range=cell_range,
                   values_only=values_only, rows=rows)
    except Exception as exc:
        return _error(str(exc))


@tool
def read_sheet_as_records(file_path: str, sheet_name: str,
                          header_row: int = 1,
                          max_rows: int = 500) -> str:
    """Read a worksheet as JSON records using header_row as column names."""
    try:
        _, wb = _load(file_path, data_only=True)
        ws = _get_sheet(wb, sheet_name)
        if header_row < 1 or header_row > ws.max_row:
            return _error("header_row varaq chegarasidan tashqarida.")
        if not 1 <= max_rows <= 5000:
            return _error("max_rows 1 dan 5000 gacha bo'lishi kerak.")
        headers = []
        for col in range(1, ws.max_column + 1):
            value = ws.cell(header_row, col).value
            headers.append(str(value).strip() if value is not None else f"column_{col}")
        records = []
        end_row = min(ws.max_row, header_row + max_rows)
        for row in range(header_row + 1, end_row + 1):
            values = [ws.cell(row, col).value for col in range(1, ws.max_column + 1)]
            if all(v is None for v in values):
                continue
            records.append({headers[c - 1]: _serialize(values[c - 1])
                            for c in range(1, ws.max_column + 1)})
        return _ok(sheet_name=sheet_name, headers=headers, records=records,
                   count=len(records), truncated=ws.max_row > end_row)
    except Exception as exc:
        return _error(str(exc))


@tool
def search_workbook(file_path: str, query: str,
                    case_sensitive: bool = False) -> str:
    """Search cell values across all worksheets and return matching cell addresses."""
    try:
        _, wb = _load(file_path, data_only=True)
        if not query:
            return _error("query bo'sh bo'lishi mumkin emas.")
        needle = query if case_sensitive else query.casefold()
        matches = []
        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value is None:
                        continue
                    value = str(_serialize(cell.value))
                    candidate = value if case_sensitive else value.casefold()
                    if needle in candidate:
                        matches.append({"sheet_name": ws.title,
                                        "cell": cell.coordinate,
                                        "value": value[:1000]})
        return _ok(query=query, matches=matches, count=len(matches))
    except Exception as exc:
        return _error(str(exc))


@tool
def create_workbook(output_path: str, sheet_name: str = "Sheet1",
                    headers_json: str = "[]",
                    rows_json: str = "[]") -> str:
    """Create a workbook with optional headers and rows supplied as JSON arrays."""
    try:
        path = _safe_path(output_path, must_exist=False, suffix=".xlsx")
        if path.exists():
            return _error("Bu fayl allaqachon mavjud. Boshqa output_path tanlang.")
        headers = json.loads(headers_json)
        rows = json.loads(rows_json)
        if not isinstance(headers, list) or not isinstance(rows, list):
            return _error("headers_json va rows_json JSON list bo'lishi kerak.")
        if any(not isinstance(row, list) for row in rows):
            return _error("rows_json ichidagi har bir element list bo'lishi kerak.")
        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name[:31] or "Sheet1"
        if headers:
            ws.append(headers)
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1F4E78")
        for row in rows:
            ws.append(row)
        ws.freeze_panes = "A2" if headers else None
        wb.save(str(path))
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_name=ws.title, rows_written=len(rows),
                   columns=len(headers) if headers else ws.max_column)
    except Exception as exc:
        return _error(str(exc))


@tool
def create_sheet(file_path: str, output_path: str,
                 sheet_name: str) -> str:
    """Add a new worksheet to an existing workbook."""
    try:
        _, wb = _load(file_path)
        name = sheet_name.strip()
        if not name or len(name) > 31 or any(ch in name for ch in r'[]:*?/\\'):
            return _error("Varaq nomi 1-31 belgidan iborat bo'lishi va []:*?/\\ belgilarini ishlatmasligi kerak.")
        if name in wb.sheetnames:
            return _error("Bunday nomli varaq allaqachon mavjud.")
        wb.create_sheet(name)
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_name=name, sheet_names=wb.sheetnames)
    except Exception as exc:
        return _error(str(exc))


@tool
def rename_sheet(file_path: str, output_path: str,
                 old_name: str, new_name: str) -> str:
    """Rename a worksheet."""
    try:
        _, wb = _load(file_path)
        ws = _get_sheet(wb, old_name)
        name = new_name.strip()
        if not name or len(name) > 31 or any(ch in name for ch in r'[]:*?/\\'):
            return _error("Yangi varaq nomi 1-31 belgidan iborat bo'lishi kerak va []:*?/\\ belgilarini ishlatmasin.")
        if name in wb.sheetnames and name != old_name:
            return _error("Bunday nomli varaq allaqachon mavjud.")
        ws.title = name
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   old_name=old_name, new_name=name)
    except Exception as exc:
        return _error(str(exc))


@tool
def delete_sheet(file_path: str, output_path: str, sheet_name: str) -> str:
    """Delete a worksheet. Refuses to delete the last remaining worksheet."""
    try:
        _, wb = _load(file_path)
        ws = _get_sheet(wb, sheet_name)
        if len(wb.worksheets) <= 1:
            return _error("Oxirgi varaqni o'chirib bo'lmaydi.")
        del wb[sheet_name]
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   deleted_sheet=sheet_name, sheet_names=wb.sheetnames)
    except Exception as exc:
        return _error(str(exc))


@tool
def write_cell(file_path: str, output_path: str, sheet_name: str,
               cell_address: str, value: Any) -> str:
    """Write a value to a cell, e.g. B3. Use a string starting with apostrophe if literal text begins with '='."""
    try:
        if not re.fullmatch(r"\$?[A-Z]{1,3}\$?\d+", cell_address.upper()):
            return _error("cell_address A1 kabi bo'lishi kerak.")
        _, wb = _load(file_path)
        ws = _get_sheet(wb, sheet_name)
        ws[cell_address] = value
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_name=sheet_name, cell=cell_address,
                   value=_serialize(value))
    except Exception as exc:
        return _error(str(exc))


@tool
def write_range(file_path: str, output_path: str, sheet_name: str,
                start_cell: str, data_json: str) -> str:
    """Write a 2D JSON array starting at a cell, e.g. start_cell='A1', data_json='[[\"Name\",\"Age\"],[\"Ali\",20]]'."""
    try:
        if not re.fullmatch(r"\$?[A-Z]{1,3}\$?\d+", start_cell.upper()):
            return _error("start_cell A1 kabi bo'lishi kerak.")
        data = json.loads(data_json)
        if not isinstance(data, list) or not all(isinstance(row, list) for row in data):
            return _error("data_json 2D JSON array bo'lishi kerak.")
        from openpyxl.utils.cell import coordinate_to_tuple
        start_row, start_col = coordinate_to_tuple(start_cell.replace("$", "").upper())
        _, wb = _load(file_path)
        ws = _get_sheet(wb, sheet_name)
        for r, row in enumerate(data):
            for c, value in enumerate(row):
                ws.cell(start_row + r, start_col + c).value = value
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_name=sheet_name, start_cell=start_cell,
                   rows_written=len(data),
                   cells_written=sum(len(row) for row in data))
    except Exception as exc:
        return _error(str(exc))


@tool
def update_cell_formula(file_path: str, output_path: str,
                        sheet_name: str, cell_address: str,
                        formula: str) -> str:
    """Write an Excel formula such as =SUM(B2:B10). openpyxl writes formulas but does not calculate them."""
    try:
        if not re.fullmatch(r"\$?[A-Z]{1,3}\$?\d+", cell_address.upper()):
            return _error("cell_address A1 kabi bo'lishi kerak.")
        if not formula.startswith("="):
            return _error("Formula '=' belgisi bilan boshlanishi kerak.")
        _, wb = _load(file_path, data_only=False)
        ws = _get_sheet(wb, sheet_name)
        ws[cell_address] = formula
        wb.calculation.fullCalcOnLoad = True
        wb.calculation.forceFullCalc = True
        wb.calculation.calcMode = "auto"
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_name=sheet_name, cell=cell_address, formula=formula,
                   note="Formulani hisoblash Excel yoki mos spreadsheet dasturi ochilganda amalga oshadi.")
    except Exception as exc:
        return _error(str(exc))


@tool
def find_and_replace_cells(file_path: str, output_path: str,
                           old_text: str, new_text: str,
                           sheet_name: str = "") -> str:
    """Replace substring in text cell values across all sheets, or only sheet_name if provided."""
    try:
        if not old_text:
            return _error("old_text bo'sh bo'lishi mumkin emas.")
        _, wb = _load(file_path, data_only=False)
        sheets = [_get_sheet(wb, sheet_name)] if sheet_name else wb.worksheets
        count = 0
        for ws in sheets:
            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str) and old_text in cell.value:
                        cell.value = cell.value.replace(old_text, new_text)
                        count += 1
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)), replacements=count)
    except Exception as exc:
        return _error(str(exc))


@tool
def insert_rows_or_columns(file_path: str, output_path: str,
                           sheet_name: str, axis: str,
                           index: int, amount: int = 1) -> str:
    """Insert rows or columns before 1-based index. Note formulas/references may not all update automatically."""
    try:
        if axis not in {"row", "column"}:
            return _error("axis 'row' yoki 'column' bo'lishi kerak.")
        if index < 1 or amount < 1 or amount > 1000:
            return _error("index kamida 1, amount esa 1-1000 oralig'ida bo'lishi kerak.")
        _, wb = _load(file_path)
        ws = _get_sheet(wb, sheet_name)
        if axis == "row":
            ws.insert_rows(index, amount)
        else:
            ws.insert_cols(index, amount)
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_name=sheet_name, axis=axis, index=index, amount=amount)
    except Exception as exc:
        return _error(str(exc))


@tool
def delete_rows_or_columns(file_path: str, output_path: str,
                           sheet_name: str, axis: str,
                           index: int, amount: int = 1) -> str:
    """Delete rows or columns starting at 1-based index. Note formulas/references may not all update automatically."""
    try:
        if axis not in {"row", "column"}:
            return _error("axis 'row' yoki 'column' bo'lishi kerak.")
        if index < 1 or amount < 1 or amount > 1000:
            return _error("index kamida 1, amount esa 1-1000 oralig'ida bo'lishi kerak.")
        _, wb = _load(file_path)
        ws = _get_sheet(wb, sheet_name)
        if axis == "row":
            ws.delete_rows(index, amount)
        else:
            ws.delete_cols(index, amount)
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_name=sheet_name, axis=axis, index=index, amount=amount)
    except Exception as exc:
        return _error(str(exc))


@tool
def style_range(file_path: str, output_path: str, sheet_name: str,
                cell_range: str, font_name: str = "Arial",
                font_size: int = 11, bold: bool = False,
                font_color: str = "#000000",
                fill_color: str = "",
                horizontal_alignment: str = "general") -> str:
    """Style a cell range with font, text color, optional fill color, and alignment."""
    try:
        if not re.fullmatch(r"[0-9a-fA-F]{6}", font_color.lstrip("#")):
            return _error("font_color 6 ta hex raqam bo'lishi kerak.")
        if fill_color and not re.fullmatch(r"[0-9a-fA-F]{6}", fill_color.lstrip("#")):
            return _error("fill_color 6 ta hex raqam yoki bo'sh qiymat bo'lishi kerak.")
        if not 1 <= font_size <= 100:
            return _error("font_size 1 dan 100 gacha bo'lishi kerak.")
        if horizontal_alignment not in {"general", "left", "center", "right", "fill", "justify"}:
            return _error("horizontal_alignment noto'g'ri.")
        _, wb = _load(file_path)
        ws = _get_sheet(wb, sheet_name)
        for row in ws[cell_range]:
            for cell in row:
                cell.font = copy(cell.font)
                cell.font = Font(
                    name=font_name, size=font_size, bold=bold,
                    italic=cell.font.italic, underline=cell.font.underline,
                    color=font_color.lstrip("#").upper()
                )
                if fill_color:
                    cell.fill = PatternFill("solid", fgColor=fill_color.lstrip("#").upper())
                cell.alignment = copy(cell.alignment)
                cell.alignment = Alignment(
                    horizontal=horizontal_alignment,
                    vertical=cell.alignment.vertical,
                    wrap_text=cell.alignment.wrap_text
                )
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_name=sheet_name, cell_range=cell_range)
    except Exception as exc:
        return _error(str(exc))


@tool
def set_column_width(file_path: str, output_path: str,
                     sheet_name: str, column: str,
                     width: float) -> str:
    """Set worksheet column width, e.g. column='A', width=22."""
    try:
        if not re.fullmatch(r"[A-Z]{1,3}", column.upper()):
            return _error("column A kabi harf bo'lishi kerak.")
        if not 0 < width <= 100:
            return _error("width 0 dan katta va 100 dan oshmasligi kerak.")
        _, wb = _load(file_path)
        ws = _get_sheet(wb, sheet_name)
        ws.column_dimensions[column.upper()].width = width
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_name=sheet_name, column=column.upper(), width=width)
    except Exception as exc:
        return _error(str(exc))


@tool
def set_freeze_panes(file_path: str, output_path: str,
                     sheet_name: str, cell_address: str = "A2") -> str:
    """Freeze rows/columns above and to the left of a cell, e.g. A2 freezes the first row."""
    try:
        if not re.fullmatch(r"\$?[A-Z]{1,3}\$?\d+", cell_address.upper()):
            return _error("cell_address A1 kabi bo'lishi kerak.")
        _, wb = _load(file_path)
        ws = _get_sheet(wb, sheet_name)
        ws.freeze_panes = cell_address.upper()
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_name=sheet_name, freeze_panes=cell_address.upper())
    except Exception as exc:
        return _error(str(exc))


@tool
def add_excel_table(file_path: str, output_path: str, sheet_name: str,
                    cell_range: str, table_name: str,
                    style_name: str = "TableStyleMedium2") -> str:
    """Turn a cell range into an Excel table with filters and a named table style."""
    try:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
            return _error("table_name harf yoki underscore bilan boshlanib, faqat harf, raqam va underscore ishlatsin.")
        _, wb = _load(file_path)
        ws = _get_sheet(wb, sheet_name)
        if any(table_name in sheet.tables for sheet in wb.worksheets):
            return _error("Bunday nomli Excel jadvali allaqachon mavjud.")
        table = Table(displayName=table_name, ref=cell_range)
        table.tableStyleInfo = TableStyleInfo(
            name=style_name, showFirstColumn=False, showLastColumn=False,
            showRowStripes=True, showColumnStripes=False
        )
        ws.add_table(table)
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_name=sheet_name, table_name=table_name, cell_range=cell_range)
    except Exception as exc:
        return _error(str(exc))


@tool
def set_sheet_tab_color(file_path: str, output_path: str,
                        sheet_name: str, color_hex: str) -> str:
    """Change the worksheet tab color, using a hex color such as '#70AD47'."""
    try:
        color = color_hex.strip().lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", color):
            return _error("color_hex #RRGGBB formatida bo'lishi kerak.")
        _, wb = _load(file_path)
        ws = _get_sheet(wb, sheet_name)
        ws.sheet_properties.tabColor = color.upper()
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_name=sheet_name, tab_color="#" + color.upper())
    except Exception as exc:
        return _error(str(exc))


@tool
def copy_worksheet(file_path: str, output_path: str,
                   source_sheet: str, new_sheet_name: str) -> str:
    """Duplicate a worksheet inside the same workbook; some Excel objects may not copy."""
    try:
        _, wb = _load(file_path)
        src = _get_sheet(wb, source_sheet)
        name = new_sheet_name.strip()
        if not name or len(name) > 31 or any(ch in name for ch in r'[]:*?/\\'):
            return _error("Yangi varaq nomi 1-31 belgidan iborat bo'lishi kerak.")
        if name in wb.sheetnames:
            return _error("Bunday nomli varaq allaqachon mavjud.")
        dst = wb.copy_worksheet(src)
        dst.title = name
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   source_sheet=source_sheet, new_sheet=name)
    except Exception as exc:
        return _error(str(exc))


@tool
def save_workbook_copy(file_path: str, output_path: str) -> str:
    """Open, validate, and save a copy of an Excel workbook."""
    try:
        _, wb = _load(file_path)
        path = _save(wb, output_path)
        return _ok(file_path=str(path.relative_to(WORKSPACE)),
                   sheet_names=wb.sheetnames)
    except Exception as exc:
        return _error(str(exc))


EXCEL_TOOLS = [
    list_workbooks,
    get_workbook_info,
    read_sheet_range,
    read_sheet_as_records,
    search_workbook,
    create_workbook,
    create_sheet,
    rename_sheet,
    delete_sheet,
    write_cell,
    write_range,
    update_cell_formula,
    find_and_replace_cells,
    insert_rows_or_columns,
    delete_rows_or_columns,
    style_range,
    set_column_width,
    set_freeze_panes,
    add_excel_table,
    set_sheet_tab_color,
    copy_worksheet,
    save_workbook_copy,
]
