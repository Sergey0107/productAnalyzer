import time
from pathlib import Path
from docx import Document
from handlers.file_handler import FileHandler


class DocxHandler(FileHandler):

    def get_data_from_docx_file(self, file_path):
        start_time = time.time()

        doc = Document(file_path)
        tz_data = self.search_table(doc)

        elapsed_time = time.time() - start_time
        total_tables = len(tz_data)
        total_rows = sum(len(table) for table in tz_data)
        print(f"[DEBUG] DOCX парсинг | tables={total_tables} | rows={total_rows} | time={elapsed_time:.2f}s")

        return tz_data

    def search_table(self, doc: Document):
        tables_data = []

        for table in doc.tables:
            if len(table.rows) < 2:
                 continue

            table_rows = []

            for row in table.rows:
                row_cells = []
                for cell in row.cells:
                    text = " ".join(cell.text.split())
                    row_cells.append(text)
                table_rows.append(row_cells)

            tables_data.append(table_rows)

        return tables_data
