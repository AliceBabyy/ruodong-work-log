from datetime import date, datetime

from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DailyNote, WeeklyNote

router = APIRouter()


@router.post("/note/save")
def save_daily_note(
    note_date: str = Form(...),
    summary: str = Form(""),
    plan_tomorrow: str = Form(""),
    return_date: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """保存（或更新）某天的日小结。一天只有一条。"""
    d = date.fromisoformat(note_date)
    summary = summary.strip() or None
    plan_tomorrow = plan_tomorrow.strip() or None

    note = db.query(DailyNote).filter(DailyNote.note_date == d).one_or_none()
    if note is None:
        note = DailyNote(note_date=d)
        db.add(note)
    note.summary = summary
    note.plan_tomorrow = plan_tomorrow
    db.commit()

    redirect_date = return_date or note_date
    return RedirectResponse(f"/day/{redirect_date}/timeline", status_code=303)


@router.post("/note/week/save")
def save_weekly_note(
    week_start: str = Form(...),
    week_summary: str = Form(""),
    next_week_plan: str = Form(""),
    return_week: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """保存（或更新）某一周的周小结。一周只有一条。"""
    ws = date.fromisoformat(week_start)
    week_summary = week_summary.strip() or None
    next_week_plan = next_week_plan.strip() or None

    note = db.query(WeeklyNote).filter(WeeklyNote.week_start == ws).one_or_none()
    if note is None:
        note = WeeklyNote(week_start=ws)
        db.add(note)
    note.week_summary = week_summary
    note.next_week_plan = next_week_plan
    db.commit()

    target = return_week or week_start
    return RedirectResponse(f"/week/{target}", status_code=303)
