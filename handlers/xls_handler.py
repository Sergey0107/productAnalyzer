import time
from pathlib import Path
from typing import List, Dict, Any

from openpyxl import load_workbook

from handlers.file_handler import FileHandler


class XlsHandler(FileHandler):

    def get_data_from_xls_file(self, file_path: Path) -> List[Dict[str, Any]]:
        start_time = time.time()

        workbook = load_workbook(filename=file_path, data_only=True)
        sheets_data = []
        total_rows = 0

        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]

            sheet_rows = []
            for row in sheet.iter_rows(values_only=True):

                row_cells = [
                    str(cell).strip() if cell is not None else ""
                    for cell in row
                ]
                # Пропускаем полностью пустые строки
                if any(cell for cell in row_cells):
                    sheet_rows.append(row_cells)
                    total_rows += 1

            sheets_data.append({
                "sheet_name": sheet_name,
                "rows": sheet_rows
            })

        workbook.close()

        elapsed_time = time.time() - start_time
        print(f"[DEBUG] XLS парсинг | sheets={len(workbook.sheetnames)} | rows={total_rows} | time={elapsed_time:.2f}s")

        return sheets_data