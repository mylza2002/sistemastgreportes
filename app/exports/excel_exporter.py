from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter
from datetime import datetime
import os


def export_excel(data, columns, title):

    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte"

    # =========================
    # 🔹 TÍTULO
    # =========================
    ws.merge_cells(
        start_row=1,
        start_column=1,
        end_row=1,
        end_column=len(columns)
    )

    title_cell = ws.cell(row=1, column=1)
    title_cell.value = title
    title_cell.font = Font(size=14, bold=True)
    title_cell.alignment = Alignment(horizontal="center")

    # =========================
    # 🔹 HEADERS
    # =========================
    for col_num, (header, key) in enumerate(columns, start=1):
        cell = ws.cell(row=3, column=col_num)
        cell.value = header
        cell.font = Font(bold=True)

    # =========================
    # 🔹 DATA
    # =========================
    for row_num, row in enumerate(data, start=4):
        for col_num, (header, key) in enumerate(columns, start=1):

            value = row.get(key)

            # Formatear fechas automáticamente
            if isinstance(value, datetime):
                value = value.strftime("%Y-%m-%d %H:%M:%S")

            ws.cell(row=row_num, column=col_num, value=value)

    # =========================
    # 🔹 AUTO AJUSTE COLUMNAS (FIX ERROR)
    # =========================
    MAX_WIDTH = 40  # 👈 ancho máximo permitido
    for i, column_cells in enumerate(ws.iter_cols(min_row=3), 1):
        max_length = 0

        for cell in column_cells:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass

        adjusted_width = min(max_length + 2, MAX_WIDTH)
        col_letter = get_column_letter(i)

        ws.column_dimensions[col_letter].width = adjusted_width

    # =========================
    # 🔹 CREAR CARPETA
    # =========================
    os.makedirs("reports", exist_ok=True)

    # =========================
    # 🔹 GUARDAR ARCHIVO
    # =========================
    filename = f"reports/reporte_{int(datetime.now().timestamp())}.xlsx"

    wb.save(filename)

    return filename
    