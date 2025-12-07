import io
import time
from pathlib import Path
from typing import List, Dict, Any

import fitz
from PIL import Image, ImageEnhance, ImageFilter
from yu.extractors.csv import extract

from handlers.file_handler import FileHandler


class PdfHandler(FileHandler):

    def get_data_from_pdf_file(self, file_path: Path):
        if self.is_pdf_text_based(file_path):
            print('[DEBUG] PDF содержит текст, парсинг текстовым методом')
            return self.extract_pdf_text(file_path)
        print('[DEBUG] PDF сканированный, конвертация в изображения')
        return self.pdf_to_images(file_path)

    def pdf_to_images(self, file_path: Path) -> List[bytes]:
        start_time = time.time()

        images = []
        doc = fitz.open(file_path)
        total_pages = len(doc)

        for page_num in range(total_pages):
            page = doc.load_page(page_num)

            mat = fitz.Matrix(3.0, 3.0)
            pix = page.get_pixmap(matrix=mat)

            img_bytes = self._compress_image(pix.tobytes("png"))
            images.append(img_bytes)

        doc.close()

        elapsed_time = time.time() - start_time
        print(f"[DEBUG] PDF парсинг | mode=images | pages={total_pages} | time={elapsed_time:.2f}s")

        return images

    def _compress_image(self, png_bytes: bytes, max_size: int = 2048, quality: int = 95) -> bytes:

        img = Image.open(io.BytesIO(png_bytes))

        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        if img.mode != 'RGB':
            img = img.convert('RGB')

        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.5)  # 1.5x резкость

        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.3)  # 1.3x контраст

        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.1)  # 1.1x яркость

        buffer = io.BytesIO()

        img.save(buffer, format='PNG', optimize=True)

        return buffer.getvalue()

    def is_pdf_text_based(self, file_path: Path) -> bool:
        doc = fitz.open(file_path)
        total_chars = 0
        total_pages = len(doc)

        for page in doc:
            text = page.get_text("text")
            total_chars += len(text)

        doc.close()

        avg_chars = total_chars / max(total_pages, 1)

        return avg_chars > 30

    def extract_pdf_text(self, file_path: str | Path) -> List[Dict[str, Any]]:
        start_time = time.time()

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        doc = fitz.open(file_path)
        total_pages = len(doc)

        pages = []

        for page_number in range(total_pages):
            page = doc.load_page(page_number)
            text = page.get_text("text")  # чистый текст

            pages.append({
                "page": page_number + 1,
                "text": text.strip()
            })

        doc.close()

        elapsed_time = time.time() - start_time
        print(f"[DEBUG] PDF парсинг | mode=text | pages={total_pages} | time={elapsed_time:.2f}s")

        return pages
