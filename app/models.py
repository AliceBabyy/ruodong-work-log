from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Text, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class User(Base, TimestampMixin):
    """登录用户。username 唯一，password_hash 为 bcrypt 哈希。"""
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))


class WorkLog(Base, TimestampMixin):
    __tablename__ = "work_logs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    content: Mapped[str] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_things: Mapped[str | None] = mapped_column(Text, nullable=True)


class StudyLog(Base, TimestampMixin):
    __tablename__ = "study_logs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    content: Mapped[str] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_things: Mapped[str | None] = mapped_column(Text, nullable=True)


class RestLog(Base, TimestampMixin):
    __tablename__ = "rest_logs"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    rest_way: Mapped[str] = mapped_column(String(100))
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)


class DailyNote(Base, TimestampMixin):
    """每天的一句话总结 + 明日计划。同一用户同一天只有一条，重复提交即更新。"""
    __tablename__ = "daily_notes"
    __table_args__ = (
        UniqueConstraint("user_id", "note_date", name="uq_daily_note_user_date"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    note_date: Mapped[date] = mapped_column(Date)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_tomorrow: Mapped[str | None] = mapped_column(Text, nullable=True)


class WeeklyNote(Base, TimestampMixin):
    """每周的一句话总结 + 下周计划。同一用户同一周只有一条。"""
    __tablename__ = "weekly_notes"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start", name="uq_weekly_note_user_week"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date)
    week_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_week_plan: Mapped[str | None] = mapped_column(Text, nullable=True)


class StickyNote(Base, TimestampMixin):
    """待办/随记便签。scope=daily 挂在某天（note_date 必填）；scope=global 全局总待办（note_date 为空）。
    tag 标签：None=无（白底）、note=随记（米黄）、plan=计划（浅绿）。
    title：仅计划类便签使用，计划组标题；content 按换行拆出的每一行是一条计划项。
    checks：仅计划类便签使用，JSON 布尔数组，下标与 content 按换行拆出的行一一对应，表示该行待办是否已勾选。"""

    __tablename__ = "sticky_notes"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(16), default="daily", index=True)
    note_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    tag: Mapped[str | None] = mapped_column(String(16), nullable=True)
    checks: Mapped[str | None] = mapped_column(Text, nullable=True)
