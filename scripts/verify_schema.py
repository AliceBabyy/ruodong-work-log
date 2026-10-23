"""迁移结果与幂等性验证脚本（一次性验证用，可重复执行）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import settings  # noqa: E402

e = create_engine(settings.DATABASE_URL)
c = e.connect()
try:
    print("--- users ---")
    print(c.execute(text("select id, username, left(password_hash, 20) from users")).fetchall())

    print("--- 各表 user_id 相关约束/索引 ---")
    rows = c.execute(
        text(
            "select conrelid::regclass::text, conname, pg_get_constraintdef(oid) "
            "from pg_constraint where connamespace='public'::regnamespace "
            "and (conname like 'uq_%' or conname like 'fk_%') order by conname"
        )
    ).fetchall()
    for r in rows:
        print(r)
    idx_rows = c.execute(
        text(
            "select tablename, indexname from pg_indexes "
            "where schemaname='public' and indexname like 'ix_%_user_id' order by indexname"
        )
    ).fetchall()
    for r in idx_rows:
        print(r)

    print("--- 存量数据归属统计 ---")
    for t in ["work_logs", "study_logs", "rest_logs", "daily_notes", "weekly_notes", "sticky_notes"]:
        n = c.execute(text(f"select count(*) from {t} where user_id=1")).scalar()
        total = c.execute(text(f"select count(*) from {t}")).scalar()
        print(f"{t}: {n}/{total} 条归属 admin")
finally:
    c.close()
