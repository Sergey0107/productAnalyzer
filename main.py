import time
import secrets
import json
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request, Response, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import os
from typing import Optional
from datetime import datetime

from handlers.file_handler import FileHandler
from config import settings
from utils.json_flattener import flatten_json
from db.database import engine, Base, SessionLocal
from models.models import User, Analysis, AnalysisStatus, FieldVerification
from db.security import verify_password
from pydantic import BaseModel

from celery_app import celery_app
from tasks.analysis_task import process_analysis_task

app = FastAPI(
    title="Product Analyze",
    description="API для анализа соответствия изделий техническим требованиям",
)

sessions = {}
SESSION_TIMEOUT = 24 * 3600


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db=None):
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


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    public_paths = ["/login", "/static", "/favicon.ico", "/api/login"]

    is_api_request = request.url.path.startswith("/api/") and request.url.path != "/api/login"
    is_html_request = "text/html" in request.headers.get("accept", "")

    if is_api_request:
        db = SessionLocal()
        try:
            user = get_current_user(request, db)
            if not user:
                return JSONResponse(
                    status_code=401,
                    content={"success": False, "error": "Требуется авторизация"}
                )
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


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
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


@app.get("/api/analyses")
async def get_analyses(request: Request, db=Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Требуется авторизация"}
        )

    analyses = db.query(Analysis).filter(
        Analysis.user_id == user.id
    ).order_by(Analysis.id.desc()).all()

    return JSONResponse(content={
        "success": True,
        "analyses": [
            {
                "id": a.id,
                "tz_filename": a.tz_filename,
                "passport_filename": a.passport_filename,
                "status": a.status.value,
                "comparison_mode": a.comparison_mode,
                "user_id": a.user_id,
                "celery_task_id": getattr(a, 'celery_task_id', None)
            }
            for a in analyses
        ]
    })


@app.get("/api/analysis/{analysis_id}")
async def get_analysis(
        analysis_id: int,
        request: Request,
        db=Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Требуется авторизация"}
        )

    analysis = (
        db.query(Analysis)
        .filter(
            Analysis.id == analysis_id,
            Analysis.user_id == user.id
        )
        .first()
    )

    if not analysis:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Анализ не найден"}
        )

    fields = (
        db.query(FieldVerification)
        .filter(FieldVerification.analysis_id == analysis.id)
        .order_by(FieldVerification.id)
        .all()
    )

    field_items = []
    for f in fields:
        field_items.append({
            "field_key": f.field_key,
            "tz_value": f.tz_value,
            "passport_value": f.passport_value,
            "quote": f.quote,
            "auto_match": f.auto_match,
            "manual_verification": f.manual_verification,
            "specialist_comment": f.specialist_comment,
        })

    return {
        "success": True,
        "analysis": {
            "id": analysis.id,
            "tz_filename": analysis.tz_filename,
            "passport_filename": analysis.passport_filename,
            "status": analysis.status.value,
            "comparison_mode": analysis.comparison_mode,
        },
        "fields": field_items,
    }


@app.post("/api/analysis/create")
async def create_analysis(
        request: Request,
        tz_file: UploadFile = File(...),
        passport_file: UploadFile = File(...),
        comparison_mode: str = Form("flexible"),
        db=Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Требуется авторизация"}
        )

    try:
        file_handler = FileHandler()
        file_handler.validate_file(tz_file)
        file_handler.validate_file(passport_file)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": str(e)}
        )

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

    print(f"✅ Анализ создан в БД: ID={analysis.id}, user_id={analysis.user_id}")

    check = db.query(Analysis).filter(Analysis.id == analysis.id).first()
    if check:
        print(f"✅ Проверка: анализ {analysis.id} найден в БД")
    else:
        print(f"❌ ОШИБКА: анализ {analysis.id} НЕ найден в БД после commit!")

    tz_filename = f"tz_{analysis.id}_{tz_file.filename}"
    passport_filename = f"passport_{analysis.id}_{passport_file.filename}"

    tz_path = Path(settings.UPLOAD_DIR) / tz_filename
    passport_path = Path(settings.UPLOAD_DIR) / passport_filename

    file_handler = FileHandler()
    file_handler.save_upload_file(tz_file, tz_path)
    file_handler.save_upload_file(passport_file, passport_path)

    task = process_analysis_task.apply_async(
        args=[analysis.id, str(tz_path), str(passport_path), comparison_mode],
        task_id=f"analysis_{analysis.id}"
    )

    return JSONResponse(content={
        "success": True,
        "analysis_id": analysis.id,
        "task_id": task.id,
        "message": "Анализ создан и отправлен на обработку"
    })


@app.get("/api/analysis/{analysis_id}/status")
async def get_analysis_task_status(
        request: Request,
        analysis_id: int,
        db=Depends(get_db)
):
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

    task_id = f"analysis_{analysis_id}"
    task_result = celery_app.AsyncResult(task_id)

    return JSONResponse(content={
        "success": True,
        "analysis_id": analysis_id,
        "task_id": task_id,
        "task_state": task_result.state,
        "task_info": task_result.info if task_result.info else {},
        "db_status": analysis.status.value
    })


@app.delete("/api/analysis/{analysis_id}")
async def delete_analysis(request: Request, analysis_id: int, db=Depends(get_db)):
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

    field_verification = db.query(FieldVerification).filter(
        FieldVerification.analysis_id == analysis_id,
        FieldVerification.field_key == data.field_key
    ).first()

    if field_verification:
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
    user = get_current_user(request, db)
    if not user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": "Требуется авторизация"}
        )

    analysis = (
        db.query(Analysis)
        .filter(
            Analysis.id == analysis_id,
            Analysis.user_id == user.id
        )
        .first()
    )

    if not analysis:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Анализ не найден"}
        )

    field_verifications = (
        db.query(FieldVerification)
        .filter(FieldVerification.analysis_id == analysis_id)
        .order_by(FieldVerification.id)
        .all()
    )

    items = []
    for fv in field_verifications:
        items.append({
            "id": fv.id,
            "field_key": fv.field_key,
            "tz_value": fv.tz_value,
            "passport_value": fv.passport_value,
            "quote": fv.quote,
            "auto_match": fv.auto_match,
            "manual_verification": fv.manual_verification,
            "specialist_comment": fv.specialist_comment,
            "updated_at": fv.updated_at.isoformat() if fv.updated_at else None,
        })

    return {
        "success": True,
        "analysis_id": analysis_id,
        "total_fields": len(items),
        "field_verifications": items,
    }


@app.get("/health")
async def health_check():
    try:
        celery_inspect = celery_app.control.inspect()
        active_workers = celery_inspect.active()
        redis_available = active_workers is not None
    except Exception:
        redis_available = False

    return {
        "status": "ok",
        "timestamp": time.time(),
        "redis_connected": redis_available
    }


@app.get("/api/user")
async def get_current_user_info(request: Request, db=Depends(get_db)):
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)