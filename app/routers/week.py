from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import DailyNote, RestLog, StudyLog, User, WeeklyNote, WorkLog

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _monday_of(d: date) -> date:
    """把任意日期对齐到它所在周的周一。weekday(): 周一=0 ... 周日=6"""
    return d - timedelta(days=d.weekday())


def _count_logs_on(db: Session, d: date, user_id: int) -> int:
    """这一天 work/study/rest 三类日志总条数（当前用户的）。"""
    day_start = datetime.combine(d, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    def _count(model):
        return db.scalar(
            select(func.count()).select_from(model).where(
                model.user_id == user_id,
                model.start_time >= day_start,
                model.start_time < day_end,
            )
        )

    return _count(WorkLog) + _count(StudyLog) + _count(RestLog)


@router.get("/week")
def week_today():
    """不带日期：直接跳到本周。"""
    today = date.today()
    monday = _monday_of(today)
    return RedirectResponse(f"/week/{monday.strftime('%Y-%m-%d')}", status_code=303)


@router.get("/week/{date_str}")
def week_view(
    request: Request,
    date_str: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = datetime.strptime(date_str, "%Y-%m-%d").date()
    monday = _monday_of(target)
    sunday = monday + timedelta(days=6)

    today = date.today()

    # 7 天每天的数据
    days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        note = (
            db.query(DailyNote)
            .filter(DailyNote.user_id == user.id, DailyNote.note_date == d)
            .one_or_none()
        )
        days.append({
            "date": d,
            "weekday": WEEKDAY_LABELS[i],
            "is_today": d == today,
            "is_weekend": d.weekday() >= 5,
            "note": note,
            "log_count": _count_logs_on(db, d, user.id),
        })

    # 本周小结
    week_note = (
        db.query(WeeklyNote)
        .filter(WeeklyNote.user_id == user.id, WeeklyNote.week_start == monday)
        .one_or_none()
    )

    # 上一周小结（取它的 next_week_plan，用来在本周顶部显示"上周计划本周"）
    last_monday = monday - timedelta(days=7)
    last_week_note = (
        db.query(WeeklyNote)
        .filter(WeeklyNote.user_id == user.id, WeeklyNote.week_start == last_monday)
        .one_or_none()
    )

    # 上一周/下一周导航
    prev_monday = monday - timedelta(days=7)
    next_monday = monday + timedelta(days=7)

    return templates.TemplateResponse(
        request,
        "week.html",
        {
            "monday": monday,
            "sunday": sunday,
            "today": today,
            "days": days,
            "week_note": week_note,
            "last_week_plan": last_week_note.next_week_plan if last_week_note else None,
            "prev_monday": prev_monday,
            "next_monday": next_monday,
        },
    )
