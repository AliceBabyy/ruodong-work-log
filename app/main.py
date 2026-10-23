import secrets

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app import auth
from app.auth import get_current_user
from app.config import settings
from app.database import engine
from app.models import Base
from app.routers import calendar, day, note, rest, study, todo, week, work

Base.metadata.create_all(bind=engine)

# 若 .env 未配置 SECRET_KEY，用随机值兜底（每次重启后登录态失效，建议尽快配置）
secret_key = settings.SECRET_KEY or secrets.token_hex(32)

app = FastAPI(title="工作日志")

# SameSite=Lax：阻止跨站请求携带 cookie，天然挡掉绝大多数 CSRF 表单伪造
app.add_middleware(
    SessionMiddleware,
    secret_key=secret_key,
    session_cookie="session",
    max_age=settings.SESSION_MAX_AGE,
    same_site="lax",
    https_only=settings.HTTPS_ONLY,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 登录/注册/登出本身不需要登录态
app.include_router(auth.router)

# 以下业务路由整组挂登录门禁：未登录一律 303 到 /login
login_required = [Depends(get_current_user)]

app.include_router(calendar.router, dependencies=login_required)
app.include_router(day.router, dependencies=login_required)
app.include_router(work.router, dependencies=login_required)
app.include_router(study.router, dependencies=login_required)
app.include_router(rest.router, dependencies=login_required)
app.include_router(note.router, dependencies=login_required)
app.include_router(todo.router, dependencies=login_required)
app.include_router(week.router, dependencies=login_required)
