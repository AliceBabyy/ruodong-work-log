"""用户注册 / 登录 / 登出 与登录态依赖。

认证方式：Session Cookie（Starlette SessionMiddleware 签名，SameSite=Lax）。
密码存储：bcrypt 哈希（带盐，抗暴力破解）。
权限模型：只区分“已登录 / 未登录”；数据隔离由业务路由按 user_id 过滤实现。
"""
import re

import bcrypt
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# 用户名：2-50 位，中英文、数字、下划线
USERNAME_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fa5]{2,50}$")
MIN_PASSWORD_LEN = 6


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _safe_next(next_url: str | None) -> str:
    """只允许站内相对路径，防止开放重定向。"""
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """登录态门禁依赖：已登录返回 User；未登录重定向到 /login。

    用法：
      - 作为 router 级 dependencies=[Depends(get_current_user)] 做整组门禁；
      - 在需要当前用户对象的路由函数里再声明 user: User = Depends(get_current_user)。
    """
    user_id = request.session.get("user_id")
    if user_id is None:
        path = request.url.path
        query = request.url.query
        target = f"{path}?{query}" if query else path
        raise HTTPException(
            status_code=303,
            headers={"Location": f"/login?next={target}"},
        )
    user = db.get(User, user_id)
    if user is None:
        # session 里的用户已被删除，清掉登录态
        request.session.clear()
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


@router.get("/login")
def login_page(request: Request, next: str | None = None):
    if request.session.get("user_id"):
        return RedirectResponse(_safe_next(next), status_code=303)
    return templates.TemplateResponse(
        request, "login.html", {"next": next or "", "error": None}
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str | None = Form(None),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username.strip()).one_or_none()
    # 统一提示“用户名或密码错误”，避免暴露用户名是否存在
    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"next": next or "", "error": "用户名或密码错误"},
            status_code=400,
        )
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    return RedirectResponse(_safe_next(next), status_code=303)


@router.get("/register")
def register_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request, "register.html", {"error": None, "username": ""}
    )


@router.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    username = username.strip()
    error = None
    if not USERNAME_RE.match(username):
        error = "用户名需为 2-50 位的中文、字母、数字或下划线"
    elif len(password) < MIN_PASSWORD_LEN:
        error = f"密码至少 {MIN_PASSWORD_LEN} 位"
    elif password != confirm_password:
        error = "两次输入的密码不一致"
    elif db.query(User).filter(User.username == username).one_or_none() is not None:
        error = "该用户名已被注册"

    if error:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": error, "username": username},
            status_code=400,
        )

    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
