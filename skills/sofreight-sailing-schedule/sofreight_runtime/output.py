import json
import sys
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from sofreight_runtime.paths import exports_dir


def _excel_cell(value):
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "、".join(
            "" if item is None else str(_excel_cell(item)) for item in value
        )
    return value


def print_json(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False) + "\n"
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace", newline="\n")
        except (OSError, ValueError):
            pass
        else:
            sys.stdout.write(text)
            return

    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(text.encode("utf-8", errors="replace"))
    else:
        sys.stdout.write(text)


def write_xlsx(sheets: dict[str, list[dict]], filename_prefix: str) -> Path:
    if not sheets:
        raise ValueError("sheets must not be empty")

    out_dir = exports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"{filename_prefix}-{timestamp}.xlsx"

    wb = Workbook()
    wb.remove(wb.active)

    for sheet_name, rows in sheets.items():
        ws = wb.create_sheet(title=sheet_name)
        if not rows:
            continue
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([_excel_cell(row.get(header)) for header in headers])

    wb.save(path)
    return path
