import shutil
from operator import truediv
from pathlib import Path

from fastapi import UploadFile, HTTPException

class FileHandler:
    ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.xls', '.xlsx'}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

    def __init__(self):
        pass

    @staticmethod
    def validate_file(file: UploadFile) -> bool:
        if not file:
            raise HTTPException(status_code=400, detail="Файл не предоставлен")

        if not file.filename:
            raise HTTPException(status_code=400, detail="Имя файла отсутствует")

        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in FileHandler.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимый формат файла. Разрешены: {', '.join(FileHandler.ALLOWED_EXTENSIONS)}"
            )

        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > FileHandler.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Размер файла превышает допустимый ({FileHandler.MAX_FILE_SIZE / 1024 / 1024} MB)"
            )

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Файл пустой")

        return True

    @staticmethod
    def save_upload_file(upload_file: UploadFile, destination: Path) -> None:

        try:
            with open(destination, "wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_data_from_file(file_path: Path):
        ext = file_path.suffix.lower()

        if ext in ['.docx', '.doc']:
            print(f'[DEBUG] Обработка файла: {file_path.name} | type=DOCX')
            from handlers.docx_handler import DocxHandler
            docx_handler = DocxHandler()
            return docx_handler.get_data_from_docx_file(file_path)

        if ext in ['.pdf']:
            print(f'[DEBUG] Обработка файла: {file_path.name} | type=PDF')
            from handlers.pdf_handler import PdfHandler
            pdf_handler = PdfHandler()
            return pdf_handler.get_data_from_pdf_file(file_path)

        if ext in ['.xlsx', '.xls']:
            print(f'[DEBUG] Обработка файла: {file_path.name} | type=XLS')
            from handlers.xls_handler import XlsHandler
            xls_handler = XlsHandler()
            return xls_handler.get_data_from_xls_file(file_path)

        else:
            raise HTTPException(500)