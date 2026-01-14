import time
import secrets
import json
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request, Response, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os
from typing import Optional
from datetime import datetime

from handlers.file_handler import FileHandler
from services.tz_analyzer import analyze_tz_file
from services.passport_analyzer import analyze_passport_file
from services.comparator import json_compare_specifications
from config import settings
from utils.json_flattener import flatten_json
from db.database import engine, Base
from db.database import SessionLocal
from models.models import User, Analysis, AnalysisStatus
from db.security import verify_password
from models.models import FieldVerification
from pydantic import BaseModel
from typing import Optional
from models.models import User, Analysis, AnalysisStatus, FieldVerification

from db.security import verify_password
from pydantic import BaseModel


app = FastAPI(
    title="Product Analyze",
    description="API для анализа соответствия изделий техническим требованиям",
)

# ============================================================================
# НАСТРОЙКА АВТОРИЗАЦИИ И СЕССИЙ
# ============================================================================

sessions = {}
SESSION_TIMEOUT = 24 * 3600


def get_db():
    """Зависимость для получения сессии базы данных"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db=None):
    """Получение текущего пользователя из сессии"""
    if db is None:
        db = SessionLocal()
        try:
            return get_current_user(request, db)
        finally:
            db.close()

    user_id = request.cookies.get("user_id")
    session_token = request.cookies.get("session_token")

    if not user_id or not session_token:
        return None

    session_data = sessions.get(user_id)
    if not session_data:
        return None

    if session_data.get("token") != session_token:
        return None

    if time.time() - session_data.get("created_at", 0) > SESSION_TIMEOUT:
        del sessions[user_id]
        return None

    try:
        user_id_int = int(user_id.replace("user_", ""))
    except ValueError:
        return None

    user = db.query(User).filter(User.id == user_id_int).first()
    if not user:
        del sessions[user_id]
        return None

    return user


# ============================================================================
# MIDDLEWARE ДЛЯ ПРОВЕРКИ АВТОРИЗАЦИИ
# ============================================================================

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Middleware для проверки авторизации"""
    public_paths = ["/login", "/static", "/favicon.ico", "/api/login"]

    is_api_request = request.url.path.startswith("/api/") and request.url.path != "/api/login"
    is_html_request = "text/html" in request.headers.get("accept", "")

    if is_api_request:
        db = SessionLocal()
        try:
            user = get_current_user(request, db)
            if not user:
                response = JSONResponse(
                    status_code=401,
                    content={"success": False, "error": "Требуется авторизация"}
                )
                return response
        finally:
            db.close()

    response = await call_next(request)

    if (is_html_request and
            request.url.path not in public_paths and
            request.url.path != "/" and
            response.status_code == 200):

        db = SessionLocal()
        try:
            user = get_current_user(request, db)
            if not user:
                return RedirectResponse("/login", status_code=302)
        finally:
            db.close()

    return response


# ============================================================================
# ОСНОВНЫЕ МАРШРУТЫ
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Главная страница - дашборд с анализами"""
    db = SessionLocal()
    try:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=302)

        html_file = Path("templates/dashboard.html")
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    finally:
        db.close()


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница авторизации"""
    db = SessionLocal()
    try:
        user = get_current_user(request, db)
        if user:
            return RedirectResponse("/", status_code=302)

        html_file = Path("templates/login.html")
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    finally:
        db.close()


@app.get("/new-analysis", response_class=HTMLResponse)
async def new_analysis_page(request: Request):
    """Страница создания нового анализа"""
    db = SessionLocal()
    try:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=302)

        html_file = Path("templates/new_analysis.html")
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    finally:
        db.close()


@app.get("/analysis/{analysis_id}", response_class=HTMLResponse)
async def analysis_result_page(request: Request, analysis_id: int):
    """Страница результата анализа"""
    db = SessionLocal()
    try:
        user = get_current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=302)

        analysis = db.query(Analysis).filter(
            Analysis.id == analysis_id,
            Analysis.user_id == user.id
        ).first()

        if not analysis:
            raise HTTPException(status_code=404, detail="Анализ не найден")

        html_file = Path("templates/result.html")
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    finally:
        db.close()


@app.post("/api/login")
async def api_login(
        request: Request,
        response: Response,
        username: str = Form(...),
        password: str = Form(...),
        db=Depends(get_db)
):
    """API для авторизации"""
    user = db.query(User).filter(User.username == username).first()

    if not user or not verify_password(password, user.password_hash):
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Неверный логин или пароль"}
        )

    user_id = f"user_{user.id}"
    session_token = secrets.token_urlsafe(32)

    sessions[user_id] = {
        "user_id": user.id,
        "username": user.username,
        "token": session_token,
        "created_at": time.time()
    }

    json_response = JSONResponse(
        content={"success": True, "message": "Авторизация успешна", "user": user.username}
    )

    json_response.set_cookie(
        key="user_id",
        value=user_id,
        httponly=True,
        max_age=SESSION_TIMEOUT,
        samesite="lax"
    )
    json_response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        max_age=SESSION_TIMEOUT,
        samesite="lax"
    )

    return json_response


@app.get("/api/logout")
async def api_logout(request: Request):
    """API для выхода из системы"""
    user_id = request.cookies.get("user_id")

    if user_id and user_id in sessions:
        del sessions[user_id]

    json_response = JSONResponse(
        content={"success": True, "message": "Выход выполнен"}
    )
    json_response.delete_cookie("user_id")
    json_response.delete_cookie("session_token")

    return json_response


@app.get("/api/check-auth")
async def check_auth(request: Request, db=Depends(get_db)):
    """Проверка статуса авторизации"""
    user = get_current_user(request, db)
    if user:
        return JSONResponse(
            content={
                "authenticated": True,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email
                }
            }
        )
    else:
        return JSONResponse(
            content={"authenticated": False},
            status_code=401
        )


# ============================================================================
# API - УПРАВЛЕНИЕ АНАЛИЗАМИ
# ============================================================================

@app.get("/api/analyses")
async def get_analyses(request: Request, db=Depends(get_db)):
    """Получить список всех анализов пользователя"""
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Требуется авторизация"}
        )

    analyses = db.query(Analysis).filter(
        Analysis.user_id == user.id
    ).order_by(Analysis.created_at.desc()).all()

    return JSONResponse(content={
        "success": True,
        "analyses": [
            {
                "id": a.id,
                "tz_filename": a.tz_filename,
                "passport_filename": a.passport_filename,
                "status": a.status.value,
                "comparison_mode": a.comparison_mode,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                "processing_time": a.processing_time,
                "error_message": a.error_message
            }
            for a in analyses
        ]
    })


@app.get("/api/analysis/{analysis_id}")
async def get_analysis(request: Request, analysis_id: int, db=Depends(get_db)):
    """Получить детальную информацию об анализе"""
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Требуется авторизация"}
        )

    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id
    ).first()

    if not analysis:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Анализ не найден"}
        )

    return JSONResponse(content={
        "success": True,
        "analysis": {
            "id": analysis.id,
            "tz_filename": analysis.tz_filename,
            "passport_filename": analysis.passport_filename,
            "status": analysis.status.value,
            "comparison_mode": analysis.comparison_mode,
            "tz_data": json.loads(analysis.tz_data) if analysis.tz_data else None,
            "passport_data": json.loads(analysis.passport_data) if analysis.passport_data else None,
            "comparison_result": json.loads(analysis.comparison_result) if analysis.comparison_result else None,
            "manual_verification": analysis.manual_verification,
            "comment": analysis.comment,
            "processing_time": analysis.processing_time,
            "error_message": analysis.error_message,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
            "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None
        }
    })


@app.post("/api/analysis/create")
async def create_analysis(
        request: Request,
        background_tasks: BackgroundTasks,
        tz_file: UploadFile = File(...),
        passport_file: UploadFile = File(...),
        comparison_mode: str = Form("flexible"),
        db=Depends(get_db)
):
    """Создать новый анализ"""
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Требуется авторизация"}
        )

    # Валидация файлов
    try:
        file_handler = FileHandler()
        file_handler.validate_file(tz_file)
        file_handler.validate_file(passport_file)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(e)}
        )

    # Создаем запись в БД
    analysis = Analysis(
        user_id=user.id,
        tz_filename=tz_file.filename,
        passport_filename=passport_file.filename,
        comparison_mode=comparison_mode,
        status=AnalysisStatus.PROCESSING
    )

    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    # Сохраняем файлы во временную папку
    tz_filename = f"tz_{analysis.id}_{tz_file.filename}"
    passport_filename = f"passport_{analysis.id}_{passport_file.filename}"

    tz_path = Path(settings.UPLOAD_DIR) / tz_filename
    passport_path = Path(settings.UPLOAD_DIR) / passport_filename

    file_handler = FileHandler()
    file_handler.save_upload_file(tz_file, tz_path)
    file_handler.save_upload_file(passport_file, passport_path)

    # Запускаем обработку в фоне
    background_tasks.add_task(
        process_analysis_background,
        analysis.id,
        str(tz_path),
        str(passport_path),
        comparison_mode
    )

    return JSONResponse(content={
        "success": True,
        "analysis_id": analysis.id,
        "message": "Анализ создан и отправлен на обработку"
    })


def process_analysis_background(analysis_id: int, tz_path: str, passport_path: str, comparison_mode: str):
    """Фоновая обработка анализа (синхронная функция)"""
    db = SessionLocal()
    start_time = time.time()

    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return

        # Анализ файлов
        tz_data = analyze_tz_file(Path(tz_path))
        passport_data = analyze_passport_file(Path(passport_path))

        tz_data_flat = flatten_json(tz_data)
        passport_data_flat = flatten_json(passport_data)

        comparison_result = json_compare_specifications(
            tz_data,
            passport_data,
            comparison_mode
        )

        # Обновляем результаты
        end_time = time.time()
        processing_time = int(end_time - start_time)

        analysis.tz_data = json.dumps(tz_data_flat, ensure_ascii=False)
        analysis.passport_data = json.dumps(passport_data_flat, ensure_ascii=False)
        analysis.comparison_result = json.dumps(comparison_result, ensure_ascii=False)
        analysis.processing_time = processing_time
        analysis.status = AnalysisStatus.COMPLETED
        analysis.completed_at = datetime.utcnow()

        db.commit()

    except Exception as e:
        # Обработка ошибок
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if analysis:
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(e)
            db.commit()

    finally:
        # Очистка файлов
        try:
            if os.path.exists(tz_path):
                os.remove(tz_path)
            if os.path.exists(passport_path):
                os.remove(passport_path)
        except Exception:
            pass

        db.close()


@app.patch("/api/analysis/{analysis_id}")
async def update_analysis(
        request: Request,
        analysis_id: int,
        manual_verification: Optional[bool] = Form(None),
        comment: Optional[str] = Form(None),
        db=Depends(get_db)
):
    """Обновить комментарий и ручную проверку анализа"""
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Требуется авторизация"}
        )

    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id
    ).first()

    if not analysis:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Анализ не найден"}
        )

    # Обновляем поля
    if manual_verification is not None:
        analysis.manual_verification = manual_verification

    if comment is not None:
        analysis.comment = comment

    analysis.updated_at = datetime.utcnow()
    db.commit()

    return JSONResponse(content={
        "success": True,
        "message": "Анализ обновлен",
        "manual_verification": analysis.manual_verification,
        "comment": analysis.comment
    })


@app.delete("/api/analysis/{analysis_id}")
async def delete_analysis(request: Request, analysis_id: int, db=Depends(get_db)):
    """Удалить анализ"""
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Требуется авторизация"}
        )

    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id
    ).first()

    if not analysis:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Анализ не найден"}
        )

    db.delete(analysis)
    db.commit()

    return JSONResponse(content={
        "success": True,
        "message": "Анализ удален"
    })


class FieldVerificationUpdate(BaseModel):
    field_key: str
    tz_value: Optional[str] = None
    passport_value: Optional[str] = None
    quote: Optional[str] = None
    auto_match: Optional[bool] = None
    manual_verification: Optional[bool] = None
    specialist_comment: Optional[str] = None


@app.post("/api/analysis/{analysis_id}/field-verification")
async def update_field_verification(
        request: Request,
        analysis_id: int,
        data: FieldVerificationUpdate,
        db=Depends(get_db)
):
    """Обновить или создать ручную проверку для конкретного поля"""
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Требуется авторизация"}
        )

    # Проверяем, что анализ принадлежит пользователю
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id
    ).first()

    if not analysis:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Анализ не найден"}
        )

    # Ищем существующую проверку поля
    field_verification = db.query(FieldVerification).filter(
        FieldVerification.analysis_id == analysis_id,
        FieldVerification.field_key == data.field_key
    ).first()

    if field_verification:
        # Обновляем существующую запись
        if data.tz_value is not None:
            field_verification.tz_value = data.tz_value
        if data.passport_value is not None:
            field_verification.passport_value = data.passport_value
        if data.quote is not None:
            field_verification.quote = data.quote
        if data.auto_match is not None:
            field_verification.auto_match = data.auto_match
        if data.manual_verification is not None:
            field_verification.manual_verification = data.manual_verification
        if data.specialist_comment is not None:
            field_verification.specialist_comment = data.specialist_comment
        field_verification.updated_at = datetime.utcnow()
    else:
        # Создаем новую запись
        field_verification = FieldVerification(
            analysis_id=analysis_id,
            field_key=data.field_key,
            tz_value=data.tz_value,
            passport_value=data.passport_value,
            quote=data.quote,
            auto_match=data.auto_match,
            manual_verification=data.manual_verification,
            specialist_comment=data.specialist_comment
        )
        db.add(field_verification)

    db.commit()
    db.refresh(field_verification)

    return JSONResponse(content={
        "success": True,
        "message": "Проверка поля обновлена",
        "field_verification": {
            "id": field_verification.id,
            "field_key": field_verification.field_key,
            "tz_value": field_verification.tz_value,
            "passport_value": field_verification.passport_value,
            "quote": field_verification.quote,
            "auto_match": field_verification.auto_match,
            "manual_verification": field_verification.manual_verification,
            "specialist_comment": field_verification.specialist_comment,
            "updated_at": field_verification.updated_at.isoformat()
        }
    })


@app.get("/api/analysis/{analysis_id}/field-verifications")
async def get_field_verifications(
        request: Request,
        analysis_id: int,
        db=Depends(get_db)
):
    """Получить все проверки полей для анализа"""
    try:
        user = get_current_user(request, db)
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Требуется авторизация"}
            )

        # Проверяем, что анализ принадлежит пользователю
        analysis = db.query(Analysis).filter(
            Analysis.id == analysis_id,
            Analysis.user_id == user.id
        ).first()

        if not analysis:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Анализ не найден"}
            )

        # Получаем все проверки полей
        field_verifications = db.query(FieldVerification).filter(
            FieldVerification.analysis_id == analysis_id
        ).all()

        # Формируем словарь для быстрого доступа
        verifications_dict = {}
        for fv in field_verifications:
            verifications_dict[fv.field_key] = {
                "id": fv.id,
                "tz_value": fv.tz_value,
                "passport_value": fv.passport_value,
                "quote": fv.quote,
                "auto_match": fv.auto_match,
                "manual_verification": fv.manual_verification,
                "specialist_comment": fv.specialist_comment,
                "updated_at": fv.updated_at.isoformat() if fv.updated_at else None
            }

        return JSONResponse(content={
            "success": True,
            "field_verifications": verifications_dict
        })

    except Exception as e:
        print(f"Error in get_field_verifications: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Ошибка сервера: {str(e)}"}
        )


@app.post("/api/analysis/{analysis_id}/save-all-fields")
async def save_all_field_verifications(
        request: Request,
        analysis_id: int,
        db=Depends(get_db)
):
    """Сохранить все поля из результатов сравнения в таблицу field_verifications"""
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Требуется авторизация"}
        )

    # Проверяем, что анализ принадлежит пользователю
    analysis = db.query(Analysis).filter(
        Analysis.id == analysis_id,
        Analysis.user_id == user.id
    ).first()

    if not analysis:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Анализ не найден"}
        )

    if not analysis.comparison_result:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Нет результатов сравнения"}
        )

    try:
        comparison_data = json.loads(analysis.comparison_result)
        comparisons = comparison_data.get("comparisons", [])

        saved_count = 0

        for item in comparisons:
            field_key = item.get("key", "")
            if not field_key:
                continue

            # Проверяем, существует ли уже запись
            existing = db.query(FieldVerification).filter(
                FieldVerification.analysis_id == analysis_id,
                FieldVerification.field_key == field_key
            ).first()

            if not existing:
                # Создаем новую запись только если её нет
                field_verification = FieldVerification(
                    analysis_id=analysis_id,
                    field_key=field_key,
                    tz_value=str(item.get("tz_value", "")),
                    passport_value=str(item.get("passport_value", "")),
                    quote=item.get("quote", ""),
                    auto_match=item.get("match", None)
                )
                db.add(field_verification)
                saved_count += 1

        db.commit()

        return JSONResponse(content={
            "success": True,
            "message": f"Сохранено {saved_count} полей",
            "saved_count": saved_count
        })

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Ошибка сохранения: {str(e)}"}
        )
# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ СЕРВИСНЫЕ ЭНДПОИНТЫ
# ============================================================================

@app.get("/health")
async def health_check():
    """Проверка работоспособности сервера"""
    return {"status": "ok", "timestamp": time.time()}


@app.get("/api/user")
async def get_current_user_info(request: Request, db=Depends(get_db)):
    """Получение информации о текущем пользователе"""
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Требуется авторизация"}
        )

    return JSONResponse(content={
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None
    })


# ============================================================================
# НАСТРОЙКА CORS И СТАТИЧЕСКИХ ФАЙЛОВ
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ============================================================================
# ЗАПУСК ПРИЛОЖЕНИЯ
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)