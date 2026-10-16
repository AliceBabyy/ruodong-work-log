from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import engine
from app.models import Base
from app.routers import calendar, day, note, rest, study, todo, week, work

Base.metadata.create_all(bind=engine)

app = FastAPI(title="工作日志")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(calendar.router)
app.include_router(day.router)
app.include_router(work.router)
app.include_router(study.router)
app.include_router(rest.router)
app.include_router(note.router)
app.include_router(todo.router)
app.include_router(week.router)
