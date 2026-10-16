from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DailyNote, RestLog, StudyLog, WorkLog

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_day_logs(db: Session, target_date: date):
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    work_logs = (
        db.query(WorkLog)
        .where(WorkLog.start_time >= day_start, WorkLog.start_time < day_end)
        .order_by(WorkLog.start_time)
        .all()
    )
    study_logs = (
        db.query(StudyLog)
        .where(StudyLog.start_time >= day_start, StudyLog.start_time < day_end)
        .order_by(StudyLog.start_time)
        .all()
    )
    rest_logs = (
        db.query(RestLog)
        .where(RestLog.start_time >= day_start, RestLog.start_time < day_end)
        .order_by(RestLog.start_time)
        .all()
    )
    return work_logs, study_logs, rest_logs


def _get_notes(db: Session, target_date: date):
    """返回 (当天的 DailyNote, 昨天的 plan_tomorrow)。"""
    today_note = (
        db.query(DailyNote).filter(DailyNote.note_date == target_date).one_or_none()
    )
    yesterday = target_date - timedelta(days=1)
    yesterday_note = (
        db.query(DailyNote).filter(DailyNote.note_date == yesterday).one_or_none()
    )
    yesterday_plan = yesterday_note.plan_tomorrow if yesterday_note else None
    return today_note, yesterday_plan


def _fmt_duration(minutes: int) -> str:
    """将分钟数格式化为 'X小时Y分' / 'X小时' / 'Y分'。"""
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}小时{m}分"
    if h:
        return f"{h}小时"
    return f"{m}分"


def _compute_time_summary(work_logs, study_logs, rest_logs):
    """按 工作/学习/休息 分别聚合当日时长（分钟）与记录数。

    时长取每条记录的 (end_time - start_time)，负值（起止时间异常）按 0 处理。
    每次新增/编辑/删除记录后页面都会重新渲染，本聚合随之自动重算。
    """
    def _sum_minutes(logs):
        total = 0
        for log in logs:
            minutes = (log.end_time - log.start_time).total_seconds() / 60
            if minutes > 0:
                total += minutes
        return round(total)

    work_minutes = _sum_minutes(work_logs)
    study_minutes = _sum_minutes(study_logs)
    rest_minutes = _sum_minutes(rest_logs)
    total_minutes = work_minutes + study_minutes + rest_minutes

    return {
        "work_minutes": work_minutes,
        "work_text": _fmt_duration(work_minutes),
        "work_count": len(work_logs),
        "study_minutes": study_minutes,
        "study_text": _fmt_duration(study_minutes),
        "study_count": len(study_logs),
        "rest_minutes": rest_minutes,
        "rest_text": _fmt_duration(rest_minutes),
        "rest_count": len(rest_logs),
        "total_text": _fmt_duration(total_minutes),
        "has_records": bool(work_logs or study_logs or rest_logs),
    }


@router.get("/day/{date_str}")
def day_root(date_str: str):
    return RedirectResponse(f"/day/{date_str}/timeline", status_code=303)


@router.get("/day/{date_str}/timeline")
def timeline(request: Request, date_str: str, db: Session = Depends(get_db)):
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    work_logs, study_logs, rest_logs = _get_day_logs(db, target_date)
    today_note, yesterday_plan = _get_notes(db, target_date)

    timeline = []
    for log in work_logs:
        timeline.append({"type": "work", "data": log})
    for log in study_logs:
        timeline.append({"type": "study", "data": log})
    for log in rest_logs:
        timeline.append({"type": "rest", "data": log})
    timeline.sort(key=lambda x: x["data"].start_time)

    time_summary = _compute_time_summary(work_logs, study_logs, rest_logs)

    return templates.TemplateResponse(
        request,
        "day_timeline.html",
        {
            "current_date": target_date,
            "timeline": timeline,
            "today_note": today_note,
            "yesterday_plan": yesterday_plan,
            "time_summary": time_summary,
        },
    )


@router.get("/day/{date_str}/work")
def work_list(request: Request, date_str: str, db: Session = Depends(get_db)):
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    work_logs, _, _ = _get_day_logs(db, target_date)
    ds = target_date.strftime("%Y-%m-%d")
    return templates.TemplateResponse(
        request,
        "day_list.html",
        {
            "current_date": target_date,
            "log_type": "work",
            "type_label": "工作记录",
            "add_url": f"/work/add?date={ds}",
            "edit_url_prefix": "/work",
            "logs": work_logs,
        },
    )


@router.get("/day/{date_str}/study")
def study_list(request: Request, date_str: str, db: Session = Depends(get_db)):
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    _, study_logs, _ = _get_day_logs(db, target_date)
    ds = target_date.strftime("%Y-%m-%d")
    return templates.TemplateResponse(
        request,
        "day_list.html",
        {
            "current_date": target_date,
            "log_type": "study",
            "type_label": "学习记录",
            "add_url": f"/study/add?date={ds}",
            "edit_url_prefix": "/study",
            "logs": study_logs,
        },
    )


@router.get("/day/{date_str}/rest")
def rest_list(request: Request, date_str: str, db: Session = Depends(get_db)):
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    _, _, rest_logs = _get_day_logs(db, target_date)
    ds = target_date.strftime("%Y-%m-%d")
    return templates.TemplateResponse(
        request,
        "day_list.html",
        {
            "current_date": target_date,
            "log_type": "rest",
            "type_label": "休息记录",
            "add_url": f"/rest/add?date={ds}",
            "edit_url_prefix": "/rest",
            "logs": rest_logs,
        },
    )
