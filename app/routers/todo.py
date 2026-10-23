import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import DailyNote, StickyNote, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 总待办页「昨天的便签」默认展示的行数（每行按 5 列计）
YESTERDAY_VISIBLE_ROWS = 2
YESTERDAY_VISIBLE_COUNT = YESTERDAY_VISIBLE_ROWS * 5


def _query_notes(db: Session, scope: str, user_id: int, note_date: date | None = None):
    """按 scope 取当前用户的便签；daily 需传日期，global 取 note_date 为空的行。置顶优先，再按创建时间倒序。"""
    q = db.query(StickyNote).filter(StickyNote.scope == scope, StickyNote.user_id == user_id)
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


def _line_count(content: str) -> int:
    return len(content.split("\n"))


def _build_plan_fields(items: list[str], item_done: list[str]):
    """由逐条计划项与完成标记重建 (content, checks_json)。
    空项被过滤，剩余项顺序不变，完成状态按原下标对齐。"""
    lines = [s.strip() for s in items]
    kept: list[str] = []
    checks: list[bool] = []
    for i, s in enumerate(lines):
        if s:
            kept.append(s)
            done = item_done[i] if i < len(item_done) else "0"
            checks.append(done == "1")
    content = "\n".join(kept)
    checks_json = json.dumps(checks) if checks else None
    return content, checks_json


def _load_checks(note: StickyNote) -> list:
    if not note.checks:
        return []
    try:
        return json.loads(note.checks)
    except (TypeError, ValueError):
        return []


def _attach_checks(notes):
    """给便签附加按行拆分的勾选状态列表，供模板渲染计划待办项。"""
    for n in notes:
        n.checks_list = _load_checks(n)
    return notes


@router.get("/day/{date_str}/todos")
def day_todos(
    request: Request,
    date_str: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """某一天的待办便签页，与时间线/工作记录等同级。

    顶部会把前一天的「明日计划」（DailyNote.plan_tomorrow）作为一张
    只读的「昨日计划」便签固定置顶展示；昨天没写计划则不显示。
    """
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    notes = _attach_checks(_query_notes(db, "daily", user.id, target_date))

    yesterday = target_date - timedelta(days=1)
    yesterday_note = (
        db.query(DailyNote)
        .filter(DailyNote.user_id == user.id, DailyNote.note_date == yesterday)
        .one_or_none()
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
def todos_home(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """总待办页：昨天的便签（默认收起）+ 全局总待办。"""
    today = date.today()
    yesterday = today - timedelta(days=1)
    yesterday_notes = _attach_checks(_query_notes(db, "daily", user.id, yesterday))
    global_notes = _attach_checks(_query_notes(db, "global", user.id))
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
    content: str = Form(""),
    title: str | None = Form(None),
    items: list[str] = Form([]),
    item_done: list[str] = Form([]),
    pinned: bool = Form(False),
    tag: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if scope not in ("daily", "global"):
        raise HTTPException(status_code=400, detail="scope 不合法")
    tag = _clean_tag(tag)

    if tag == "plan":
        content, checks_json = _build_plan_fields(items, item_done)
        title = (title or "").strip() or None
    else:
        content = content.strip()
        checks_json = None
        title = None

    if not content:
        # 空内容不保存，直接跳回
        return RedirectResponse(_redirect_for(scope, note_date), status_code=303)

    note = StickyNote(
        user_id=user.id,
        scope=scope,
        note_date=date.fromisoformat(note_date) if (scope == "daily" and note_date) else None,
        title=title,
        content=content,
        pinned=pinned,
        tag=tag,
        checks=checks_json,
    )
    db.add(note)
    db.commit()
    return RedirectResponse(_redirect_for(scope, note_date), status_code=303)


def _get_owned_note(db: Session, note_id: int, user_id: int) -> StickyNote:
    """按 id 取当前用户自己的便签；不存在或不属于该用户一律 404。"""
    note = db.get(StickyNote, note_id)
    if note is None or note.user_id != user_id:
        raise HTTPException(status_code=404, detail="便签不存在")
    return note


@router.post("/todos/{note_id}/edit")
def edit_note(
    note_id: int,
    content: str = Form(""),
    title: str | None = Form(None),
    items: list[str] = Form([]),
    item_done: list[str] = Form([]),
    pinned: bool = Form(False),
    tag: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_owned_note(db, note_id, user.id)
    tag = _clean_tag(tag)

    if tag == "plan":
        content, checks_json = _build_plan_fields(items, item_done)
        note.title = (title or "").strip() or None
        note.checks = checks_json
    else:
        content = content.strip()
        note.title = None
        note.checks = None

    if content:
        note.content = content
        note.pinned = pinned
        note.tag = tag
        db.commit()
    return RedirectResponse(_back_url(note), status_code=303)


@router.post("/todos/{note_id}/delete")
def delete_note(
    note_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_owned_note(db, note_id, user.id)
    url = _back_url(note)
    db.delete(note)
    db.commit()
    return RedirectResponse(url, status_code=303)


@router.post("/todos/{note_id}/toggle-pin")
def toggle_pin(
    note_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_owned_note(db, note_id, user.id)
    note.pinned = not note.pinned
    db.commit()
    return RedirectResponse(_back_url(note), status_code=303)


@router.post("/todos/{note_id}/toggle-check")
def toggle_check(
    note_id: int,
    line: int = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """计划便签：勾选/取消某一行待办。前端 fetch 调用，不整页刷新。"""
    note = _get_owned_note(db, note_id, user.id)
    line_count = _line_count(note.content)
    if line < 0 or line >= line_count:
        raise HTTPException(status_code=400, detail="行号不合法")
    checks = _load_checks(note)
    while len(checks) <= line:
        checks.append(False)
    checks[line] = not checks[line]
    note.checks = json.dumps(checks)
    db.commit()
    return JSONResponse({"ok": True, "checked": checks[line]})
