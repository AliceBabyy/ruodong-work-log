from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DailyNote, StickyNote

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 总待办页「昨天的便签」默认展示的行数（每行按 5 列计）
YESTERDAY_VISIBLE_ROWS = 2
YESTERDAY_VISIBLE_COUNT = YESTERDAY_VISIBLE_ROWS * 5


def _query_notes(db: Session, scope: str, note_date: date | None = None):
    """按 scope 取便签；daily 需传日期，global 取 note_date 为空的行。置顶优先，再按创建时间倒序。"""
    q = db.query(StickyNote).filter(StickyNote.scope == scope)
    if note_date is not None:
        q = q.filter(StickyNote.note_date == note_date)
    else:
        q = q.filter(StickyNote.note_date.is_(None))
    return q.order_by(StickyNote.pinned.desc(), StickyNote.created_at.desc()).all()


def _back_url(note: StickyNote) -> str:
    """根据便签自身归属计算操作后跳回哪个页面。"""
    if note.scope == "global":
        return "/todos"
    return f"/day/{note.note_date.strftime('%Y-%m-%d')}/todos"


def _redirect_for(scope: str, note_date: str | None) -> str:
    if scope == "global":
        return "/todos"
    d = note_date or date.today().isoformat()
    return f"/day/{d}/todos"


def _clean_tag(tag: str | None) -> str | None:
    """标签只接受 note（随记）/ plan（计划）/ 空（无标签，白底）。"""
    tag = (tag or "").strip()
    return tag if tag in ("note", "plan") else None


@router.get("/day/{date_str}/todos")
def day_todos(request: Request, date_str: str, db: Session = Depends(get_db)):
    """某一天的待办便签页，与时间线/工作记录等同级。

    顶部会把前一天的「明日计划」（DailyNote.plan_tomorrow）作为一张
    只读的「昨日计划」便签固定置顶展示；昨天没写计划则不显示。
    """
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    notes = _query_notes(db, "daily", target_date)

    yesterday = target_date - timedelta(days=1)
    yesterday_note = (
        db.query(DailyNote).filter(DailyNote.note_date == yesterday).one_or_none()
    )
    yesterday_plan = yesterday_note.plan_tomorrow if yesterday_note else None

    return templates.TemplateResponse(
        request,
        "day_todos.html",
        {
            "current_date": target_date,
            "notes": notes,
            "yesterday_plan": yesterday_plan,
        },
    )


@router.get("/todos")
def todos_home(request: Request, db: Session = Depends(get_db)):
    """总待办页：昨天的便签（默认收起）+ 全局总待办。"""
    today = date.today()
    yesterday = today - timedelta(days=1)
    yesterday_notes = _query_notes(db, "daily", yesterday)
    global_notes = _query_notes(db, "global")
    return templates.TemplateResponse(
        request,
        "todos.html",
        {
            "today": today,
            "yesterday": yesterday,
            "yesterday_notes": yesterday_notes,
            "global_notes": global_notes,
            "visible_count": YESTERDAY_VISIBLE_COUNT,
        },
    )


@router.post("/todos/add")
def add_note(
    scope: str = Form(...),
    note_date: str | None = Form(None),
    content: str = Form(...),
    pinned: bool = Form(False),
    tag: str | None = Form(None),
    db: Session = Depends(get_db),
):
    if scope not in ("daily", "global"):
        raise HTTPException(status_code=400, detail="scope 不合法")
    content = content.strip()
    if not content:
        # 空内容不保存，直接跳回
        return RedirectResponse(_redirect_for(scope, note_date), status_code=303)

    note = StickyNote(
        scope=scope,
        note_date=date.fromisoformat(note_date) if (scope == "daily" and note_date) else None,
        content=content,
        pinned=pinned,
        tag=_clean_tag(tag),
    )
    db.add(note)
    db.commit()
    return RedirectResponse(_redirect_for(scope, note_date), status_code=303)


@router.post("/todos/{note_id}/edit")
def edit_note(
    note_id: int,
    content: str = Form(...),
    pinned: bool = Form(False),
    tag: str | None = Form(None),
    db: Session = Depends(get_db),
):
    note = db.get(StickyNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="便签不存在")
    content = content.strip()
    if content:
        note.content = content
        note.pinned = pinned
        note.tag = _clean_tag(tag)
        db.commit()
    return RedirectResponse(_back_url(note), status_code=303)


@router.post("/todos/{note_id}/delete")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.get(StickyNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="便签不存在")
    url = _back_url(note)
    db.delete(note)
    db.commit()
    return RedirectResponse(url, status_code=303)


@router.post("/todos/{note_id}/toggle-pin")
def toggle_pin(note_id: int, db: Session = Depends(get_db)):
    note = db.get(StickyNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="便签不存在")
    note.pinned = not note.pinned
    db.commit()
    return RedirectResponse(_back_url(note), status_code=303)
