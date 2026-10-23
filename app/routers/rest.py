from datetime import datetime, date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import RestLog, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_owned_log(db: Session, log_id: int, user_id: int) -> RestLog:
    """按 id 取当前用户自己的休息记录；不存在或不属于该用户一律 404。"""
    log = db.get(RestLog, log_id)
    if log is None or log.user_id != user_id:
        raise HTTPException(status_code=404, detail="记录不存在")
    return log


@router.get("/rest/add")
def add_form(request: Request, user: User = Depends(get_current_user), date: str | None = None):
    return templates.TemplateResponse(
        request,
        "form_rest.html",
        {
            "request": request,
            "title": "添加休息记录",
            "action": "/rest/add",
            "log": None,
            "return_date": date,
        },
    )


@router.post("/rest/add")
def add(
    start_time: str = Form(...),
    end_time: str = Form(...),
    rest_way: str = Form(...),
    remark: str = Form(""),
    return_date: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log = RestLog(
        user_id=user.id,
        start_time=datetime.fromisoformat(start_time),
        end_time=datetime.fromisoformat(end_time),
        rest_way=rest_way,
        remark=remark.strip() or None,
    )
    db.add(log)
    db.commit()
    redirect_date = return_date or date.today().isoformat()
    return RedirectResponse(f"/day/{redirect_date}", status_code=303)


@router.get("/rest/{log_id}/edit")
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
        "form_rest.html",
        {
            "request": request,
            "title": "编辑休息记录",
            "action": f"/rest/{log_id}/edit",
            "log": log,
            "return_date": date,
        },
    )


@router.post("/rest/{log_id}/edit")
def edit(
    log_id: int,
    start_time: str = Form(...),
    end_time: str = Form(...),
    rest_way: str = Form(...),
    remark: str = Form(""),
    return_date: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log = _get_owned_log(db, log_id, user.id)
    log.start_time = datetime.fromisoformat(start_time)
    log.end_time = datetime.fromisoformat(end_time)
    log.rest_way = rest_way
    log.remark = remark.strip() or None
    db.commit()
    redirect_date = return_date or date.today().isoformat()
    return RedirectResponse(f"/day/{redirect_date}", status_code=303)


@router.post("/rest/{log_id}/delete")
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
