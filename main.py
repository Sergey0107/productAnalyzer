import shutil
import time

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os

from handlers.file_handler import FileHandler
from services.tz_analyzer import analyze_tz_file
from services.passport_analyzer import analyze_passport_file
from services.comparator import json_compare_specifications
from config import settings
from utils.json_flattener import flatten_json

app = FastAPI(
    title="Product Analyze",
    description="API для анализа соответствия изделий техническим требованиям",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():

    html_file = Path("templates/index.html")

    if not html_file.exists():
        raise HTTPException(status_code=404, detail="Главная страница не найдена")

    return html_file.read_text(encoding="utf-8")


@app.post("/api/analyze")
async def analyze_product(
    tz_file: UploadFile = File(..., description="Файл технического задания"),
    passport_file: UploadFile = File(..., description="Файл паспорта изделия"),
    comparison_mode: str = Form("flexible", description="Режим сравнения: flexible или strict")
):
    start_time = time.time()

    try:
        file_handler = FileHandler() # мб не создавать экземпляр?
        file_handler.validate_file(tz_file)
        file_handler.validate_file(passport_file)

        tz_filename = f"tz_{tz_file.filename}"
        passport_filename = f"passport_{passport_file.filename}"

        tz_path = Path(settings.UPLOAD_DIR) / tz_filename
        passport_path = Path(settings.UPLOAD_DIR) / passport_filename

        file_handler.save_upload_file(tz_file, tz_path)
        file_handler.save_upload_file(passport_file, passport_path)

        try:
            tz_data = analyze_tz_file(tz_path)
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Ошибка при парсинге файла ТЗ: {str(e)}"
            )

        try:
            passport_data = analyze_passport_file(passport_path)
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"Ошибка при анализе паспорта: {str(e)}"
            )

        # Преобразуем данные в плоский формат для корректного отображения
        tz_data_flat = flatten_json(tz_data)
        passport_data_flat = flatten_json(passport_data)

        try:
            comparison_result = json_compare_specifications(
                tz_data,
                passport_data,
                comparison_mode
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при сравнении характеристик: {str(e)}"
            )

        end_time = time.time()
        processing_time = round(end_time - start_time, 2)

        return JSONResponse(content={
            "success": True,
            "tz_data": tz_data_flat,  # Возвращаем плоские данные для UI
            "passport_data": passport_data_flat,  # Возвращаем плоские данные для UI
            "comparison": comparison_result,
            "processing_time": processing_time  # Время обработки на сервере в секундах
        })

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )
    finally:
        try:
            if tz_path.exists():
                os.remove(tz_path)
        except Exception:
            pass

        try:
            if passport_path.exists():
                os.remove(passport_path)
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


# 1) плохо парсятся документы pdf в которых мелкий шрифт
# 2) если в ТЗ есть, а в паспорте нет - что возвращаем?
# 3) привести к единообразию json-ы
# 4) подумать над архитектурой - экземпляры, сервисы