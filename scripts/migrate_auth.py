"""存量数据迁移：为现有业务表增加 user_id 并回填到初始管理员。

幂等，可重复执行。步骤：
  1. 创建 users 表（若不存在）
  2. users 表为空时，按 .env 的 ADMIN_USERNAME / ADMIN_PASSWORD 创建初始管理员
  3. 各业务表补 user_id 列（若缺失）
  4. 存量行 user_id 回填为初始管理员
  5. user_id 置 NOT NULL，补外键与索引
  6. daily_notes / weekly_notes 重建唯一约束为 (user_id, 日期)

用法（在项目根目录）：
  .venv\\Scripts\\python scripts\\migrate_auth.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.config import settings  # noqa: E402
from app.database import engine  # noqa: E402
from app.models import Base  # noqa: E402

# 需要归属到用户的所有业务表
BUSINESS_TABLES = [
    "work_logs",
    "study_logs",
    "rest_logs",
    "daily_notes",
    "weekly_notes",
    "sticky_notes",
]

# daily/weekly 旧唯一约束名 -> 新约束名（组合唯一）
NOTE_UNIQUE_REMAP = {
    "daily_notes": ("uq_daily_note_date", "uq_daily_note_user_date"),
    "weekly_notes": ("uq_weekly_note_start", "uq_weekly_note_user_week"),
}


def _column_exists(conn, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).first()
    return row is not None


def _constraint_exists(conn, name: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM pg_constraint WHERE conname = :n "
            "AND connamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')"
        ),
        {"n": name},
    ).first()
    return row is not None


def main() -> None:
    # 建 users 表（业务表已存在，create_all 默认跳过）
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        # 2. 创建初始管理员
        admin_row = conn.execute(
            text("SELECT id FROM users ORDER BY id LIMIT 1")
        ).first()
        if admin_row is None:
            admin_id = conn.execute(
                text(
                    "INSERT INTO users (username, password_hash, created_at, updated_at) "
                    "VALUES (:u, :p, now(), now()) RETURNING id"
                ),
                {"u": settings.ADMIN_USERNAME, "p": hash_password(settings.ADMIN_PASSWORD)},
            ).scalar()
            print(f"创建初始管理员: {settings.ADMIN_USERNAME} (id={admin_id})")
        else:
            admin_id = admin_row[0]
            print(f"使用现有用户 (id={admin_id}) 作为存量数据归属")

        # 3-5. 每张业务表补列、回填、置 NOT NULL、加外键与索引
        for table in BUSINESS_TABLES:
            if not _column_exists(conn, table, "user_id"):
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN user_id INTEGER'))
                print(f"  [{table}] 已添加 user_id 列")

            conn.execute(
                text(f'UPDATE "{table}" SET user_id = :uid WHERE user_id IS NULL'),
                {"uid": admin_id},
            )
            conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN user_id SET NOT NULL'))
            print(f"  [{table}] 存量数据已归属到用户 {admin_id}，user_id 置 NOT NULL")

            fk_name = f"fk_{table}_user"
            if not _constraint_exists(conn, fk_name):
                conn.execute(
                    text(
                        f'ALTER TABLE "{table}" ADD CONSTRAINT {fk_name} '
                        "FOREIGN KEY (user_id) REFERENCES users(id)"
                    )
                )
                print(f"  [{table}] 已加外键 {fk_name}")

            idx_name = f"ix_{table}_user_id"
            conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON \"{table}\" (user_id)"
                )
            )

        # 6. 重建日小结/周小结唯一约束为 (user_id, 日期)
        for table, (old_name, new_name) in NOTE_UNIQUE_REMAP.items():
            if _constraint_exists(conn, new_name):
                print(f"  [{table}] 新唯一约束已存在，跳过")
                continue
            if _constraint_exists(conn, old_name):
                conn.execute(text(f'ALTER TABLE "{table}" DROP CONSTRAINT {old_name}'))
                print(f"  [{table}] 已删除旧唯一约束 {old_name}")
            conn.execute(
                text(
                    f'ALTER TABLE "{table}" ADD CONSTRAINT {new_name} '
                    f'UNIQUE (user_id, {"note_date" if table == "daily_notes" else "week_start"})'
                )
            )
            print(f"  [{table}] 已重建唯一约束 {new_name}")

    print("迁移完成。")


if __name__ == "__main__":
    main()
