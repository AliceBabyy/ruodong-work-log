from datetime import datetime, date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import StudyLog, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_owned_log(db: Session, log_id: int, user_id: int) -> StudyLog:
    """按 id 取当前用户自己的学习记录；不存在或不属于该用户一律 404。"""
    log = db.get(StudyLog, log_id)
    if log is None or log.user_id != user_id:
        raise HTTPException(status_code=404, detail="记录不存在")
    return log


@router.get("/study/add")
def add_form(request: Request, user: User = Depends(get_current_user), date: str | None = None):
    return templates.TemplateResponse(
        request,
        "form_log.html",
        {
            "request": request,
            "type_label": "学习",
            "title": "添加学习记录",
            "action": "/study/add",
            "log": None,
            "return_date": date,
        },
    )


@router.post("/study/add")
def add(
    request: Request,
    start_time: str = Form(...),
    end_time: str = Form(...),
    content: str = Form(...),
    result: str = Form(""),
    extra_things: str = Form(""),
    return_date: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log = StudyLog(
        user_id=user.id,
        start_time=datetime.fromisoformat(start_time),
        end_time=datetime.fromisoformat(end_time),
        content=content,
        result=result.strip() or None,
        extra_things=extra_things.strip() or None,
    )
    db.add(log)
    db.commit()
    redirect_date = return_date or date.today().isoformat()
    return RedirectResponse(f"/day/{redirect_date}", status_code=303)


@router.get("/study/{log_id}/edit")
def edit_form(
    request: Request,
    log_id: int,
    date: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log = _get_owned_log(db, log_id, user.id)
    return templates.TemplateResponse(
        request,
        "form_log.html",
        {
            "request": request,
            "type_label": "学习",
            "title": "编辑学习记录",
            "action": f"/study/{log_id}/edit",
            "log": log,
            "return_date": date,
        },
    )


@router.post("/study/{log_id}/edit")
def edit(
    log_id: int,
    start_time: str = Form(...),
    end_time: str = Form(...),
    content: str = Form(...),
    result: str = Form(""),
    extra_things: str = Form(""),
    return_date: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log = _get_owned_log(db, log_id, user.id)
    log.start_time = datetime.fromisoformat(start_time)
    log.end_time = datetime.fromisoformat(end_time)
    log.content = content
    log.result = result.strip() or None
    log.extra_things = extra_things.strip() or None
    db.commit()
    redirect_date = return_date or date.today().isoformat()
    return RedirectResponse(f"/day/{redirect_date}", status_code=303)


@router.post("/study/{log_id}/delete")
def delete(
    log_id: int,
    return_date: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log = _get_owned_log(db, log_id, user.id)
    db.delete(log)
    db.commit()
    redirect_date = return_date or date.today().isoformat()
    return RedirectResponse(f"/day/{redirect_date}", status_code=303)
