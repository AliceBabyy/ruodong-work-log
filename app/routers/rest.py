from datetime import datetime, date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RestLog

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/rest/add")
def add_form(request: Request, date: str | None = None):
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
    db: Session = Depends(get_db),
):
    log = RestLog(
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
def edit_form(request: Request, log_id: int, date: str | None = None, db: Session = Depends(get_db)):
    log = db.get(RestLog, log_id)
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
    db: Session = Depends(get_db),
):
    log = db.get(RestLog, log_id)
    log.start_time = datetime.fromisoformat(start_time)
    log.end_time = datetime.fromisoformat(end_time)
    log.rest_way = rest_way
    log.remark = remark.strip() or None
    db.commit()
    redirect_date = return_date or date.today().isoformat()
    return RedirectResponse(f"/day/{redirect_date}", status_code=303)


@router.post("/rest/{log_id}/delete")
def delete(log_id: int, return_date: str = Form(...), db: Session = Depends(get_db)):
    log = db.get(RestLog, log_id)
    db.delete(log)
    db.commit()
    redirect_date = return_date or date.today().isoformat()
    return RedirectResponse(f"/day/{redirect_date}", status_code=303)
