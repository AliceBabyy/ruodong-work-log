import calendar
from datetime import date, datetime, timedelta

import chinese_calendar as cc
from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import RestLog, StudyLog, User, WorkLog

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# chinese_calendar 返回的节日英文名 -> 中文显示名
CN_HOLIDAY_NAMES = {
    "New Year's Day": "元旦",
    "Spring Festival": "春节",
    "Tomb-Sweeping Day": "清明",
    "Labour Day": "劳动节",
    "Dragon Boat Festival": "端午",
    "Mid-Autumn Festival": "中秋",
    "National Day": "国庆",
}


def _describe_day(d: date) -> dict:
    """返回某一天在日历上需要展示的标记。超出 chinese_calendar 支持年份时静默降级。"""
    cell = {
        "date": d,
        "is_today": False,
        "is_holiday": False,
        "is_makeup_workday": False,  # 周末被调成补班上班
        "holiday_name_cn": None,
    }
    try:
        on_holiday, name_en = cc.get_holiday_detail(d)
        if on_holiday:
            cell["is_holiday"] = True
            cell["holiday_name_cn"] = CN_HOLIDAY_NAMES.get(name_en, name_en)
        # 周末但要上班 = 调休补班
        if d.weekday() >= 5 and cc.is_workday(d):
            cell["is_makeup_workday"] = True
            cell["is_holiday"] = False  # 补班日不算放假
            cell["holiday_name_cn"] = None
    except NotImplementedError:
        # 包未覆盖的年份（如未来年份），静默跳过节假日标记
        pass
    return cell


@router.get("/")
def index(
    request: Request,
    user: User = Depends(get_current_user),
    year: int | None = None,
    month: int | None = None,
    db: Session = Depends(get_db),
):
    today = date.today()
    year = year or today.year
    month = month or today.month

    # 本月起止
    start_of_month = datetime(year, month, 1)
    if month == 12:
        end_of_month = datetime(year + 1, 1, 1)
    else:
        end_of_month = datetime(year, month + 1, 1)

    # 查本月有记录的日期（当前用户的）
    def _collect_dates(model):
        rows = db.execute(
            select(model.start_time).where(
                model.user_id == user.id,
                model.start_time >= start_of_month,
                model.start_time < end_of_month,
            )
        ).scalars().all()
        return {d.date() for d in rows}

    has_record_dates = _collect_dates(WorkLog) | _collect_dates(StudyLog) | _collect_dates(RestLog)

    # 生成月历（周一开头）
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)

    # 把每个格子封装成带节假日/调休标记的 dict
    grid = []
    for week in weeks:
        row = []
        for d in week:
            cell = _describe_day(d)
            cell["in_month"] = d.month == month
            cell["is_today"] = d == today
            cell["has_record"] = d in has_record_dates
            row.append(cell)
        grid.append(row)

    # 上下月导航
    if month == 1:
        prev_date = date(year - 1, 12, 1)
        next_date = date(year, 2, 1) if month == 1 else date(year, month + 1, 1)
    else:
        prev_date = date(year, month - 1, 1)
        next_date = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)

    return templates.TemplateResponse(
        request,
        "calendar.html",
        {
            "request": request,
            "year": year,
            "month": month,
            "today": today,
            "grid": grid,
            "current_month": month,
            "prev_date": prev_date,
            "next_date": next_date,
        },
    )
