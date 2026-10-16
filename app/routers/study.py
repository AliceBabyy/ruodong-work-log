from datetime import datetime, date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StudyLog

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/study/add")
def add_form(request: Request, date: str | None = None):
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
    db: Session = Depends(get_db),
):
    log = StudyLog(
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
def edit_form(request: Request, log_id: int, date: str | None = None, db: Session = Depends(get_db)):
    log = db.get(StudyLog, log_id)
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
    db: Session = Depends(get_db),
):
    log = db.get(StudyLog, log_id)
    log.start_time = datetime.fromisoformat(start_time)
    log.end_time = datetime.fromisoformat(end_time)
    log.content = content
    log.result = result.strip() or None
    log.extra_things = extra_things.strip() or None
    db.commit()
    redirect_date = return_date or date.today().isoformat()
    return RedirectResponse(f"/day/{redirect_date}", status_code=303)


@router.post("/study/{log_id}/delete")
def delete(log_id: int, return_date: str = Form(...), db: Session = Depends(get_db)):
    log = db.get(StudyLog, log_id)
    db.delete(log)
    db.commit()
    redirect_date = return_date or date.today().isoformat()
    return RedirectResponse(f"/day/{redirect_date}", status_code=303)
