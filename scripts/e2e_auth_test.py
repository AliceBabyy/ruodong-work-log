"""端到端鉴权验证脚本（测试实例 8010 端口）。

覆盖：未登录拦截、注册、登录态访问、添加记录、登出、
     双用户数据隔离、越权访问被拒（404）、cookie SameSite、错误提示不泄露用户名。
末尾自动清理测试产生的用户与数据。可重复执行。
"""
import http.cookiejar
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE = "http://127.0.0.1:8010"
TAG = str(int(time.time()))[-6:]  # 随机后缀，保证可重复运行
U_A = f"alice_{TAG}"
U_B = f"bob_{TAG}"
PW = "test123456"
SECRET = f"ALICE-SECRET-{TAG}"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cj), NoRedirect()
)


def req(path, method="GET", data=None, follow=True, max_redirects=5):
    """返回 (status, headers, body)。follow=False 时返回第一个响应（不跟随重定向）。"""
    url = BASE + path
    body = None
    headers = {}
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    for _ in range(max_redirects + 1):
        try:
            resp = opener.open(r, timeout=10)
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                if not follow:
                    return e.code, dict(e.headers), ""
                loc = e.headers.get("Location", "")
                r = urllib.request.Request(urllib.parse.urljoin(BASE + path, loc))
                continue
            return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    return None, {}, ""


passed = []
failed = []


def check(name, cond, detail=""):
    if cond:
        passed.append(name)
        print(f"  PASS  {name}")
    else:
        failed.append(name)
        print(f"  FAIL  {name}  {detail}")


def session_cookie():
    for c in cj:
        if c.name == "session":
            return c
    return None


print(f"== 1. 未登录拦截 (tag={TAG}) ==")
s, h, b = req("/", follow=False)
loc = h.get("Location") or h.get("location") or ""
check("未登录访问 / 被 303", s == 303, f"status={s}")
check("重定向到 /login", loc.startswith("/login"), loc)

print("== 2. 注册 alice 并添加工作记录 ==")
s, h, b = req("/register", "POST", {
    "username": U_A, "password": PW, "confirm_password": PW,
}, follow=False)
check("注册 alice 成功(303)", s == 303, f"status={s}")
s, h, b = req("/", follow=False)
check("alice 已登录访问 / 直接 200", s == 200, f"status={s}")
s, h, b = req("/")
check("页面包含 alice 用户名", U_A in b, "用户名未显示")

today = date.today().isoformat()
s, h, b = req("/work/add", "POST", {
    "start_time": f"{today}T09:00:00",
    "end_time": f"{today}T10:00:00",
    "content": SECRET,
    "result": "",
    "extra_things": "",
    "return_date": today,
}, follow=False)
check("alice 添加工作记录(303)", s == 303, f"status={s}")
s, h, b = req(f"/day/{today}/work")
check("alice 列表页能看到自己的记录", SECRET in b, "内容缺失")

print("== 3. alice 登出，注册 bob ==")
s, h, b = req("/logout", "POST", follow=False)
check("alice 登出(303)", s == 303, f"status={s}")
s, h, b = req("/register", "POST", {
    "username": U_B, "password": PW, "confirm_password": PW,
}, follow=False)
check("注册 bob 成功(303)", s == 303, f"status={s}")

print("== 4. bob 的数据隔离 ==")
s, h, b = req(f"/day/{today}/work")
check("bob 列表页看不到 alice 的记录", SECRET not in b, "越权泄露!")

import sqlalchemy as sa  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from app.config import settings  # noqa: E402
eng = create_engine(settings.DATABASE_URL)
with eng.connect() as conn:
    row = conn.execute(
        text("select w.id from work_logs w join users u on u.id=w.user_id "
             "where w.content like :c order by w.id desc limit 1"),
        {"c": f"%{SECRET}%"},
    ).first()
alice_log_id = row[0] if row else None
check("能定位 alice 的记录 id", alice_log_id is not None, f"row={row}")

if alice_log_id:
    s, h, b = req(f"/work/{alice_log_id}/edit", follow=False)
    check("bob 访问 alice 记录编辑页被 404", s == 404, f"status={s}")
    s, h, b = req(f"/work/{alice_log_id}/delete", "POST", {"return_date": today}, follow=False)
    check("bob 删除 alice 记录被 404", s == 404, f"status={s}")

print("== 5. cookie 属性 ==")
c = session_cookie()
check("存在 session cookie", c is not None)
# 直接抓登录响应里的原始 Set-Cookie，检查浏览器可见的属性
s, h, b = req("/login", "POST", {"username": U_A, "password": PW}, follow=False)
set_cookie = ""
for k, v in h.items():
    if k.lower() == "set-cookie":
        set_cookie = v
check("Set-Cookie 包含 SameSite=Lax", "samesite=lax" in set_cookie.lower(), set_cookie[:120])
check("Set-Cookie 包含 HttpOnly", "httponly" in set_cookie.lower(), set_cookie[:120])
check("Set-Cookie 包含登录态有效期", "max-age=" in set_cookie.lower(), set_cookie[:120])

print("== 6. 错误提示不泄露用户名 ==")
s, h, b = req("/login", "POST", {"username": "no_such_user_xyz", "password": "wrong"}, follow=False)
check("不存在用户登录提示统一(400)", s == 400, f"status={s}")
check("提示为通用文案", "用户名或密码错误" in b)
check("不泄露\"用户名不存在\"", "不存在" not in b)

print("== 7. 清理测试数据 ==")
from app.database import engine as app_engine  # noqa: E402
with app_engine.begin() as conn:
    for u in (U_A, U_B):
        uid = conn.execute(text("select id from users where username=:u"), {"u": u}).scalar()
        if uid is None:
            continue
        for t in ["work_logs", "study_logs", "rest_logs", "daily_notes", "weekly_notes", "sticky_notes"]:
            conn.execute(text(f'delete from "{t}" where user_id=:uid'), {"uid": uid})
        conn.execute(text("delete from users where id=:uid"), {"uid": uid})
        print(f"  已清理用户 {u} 及其数据")

print()
print(f"结果: {len(passed)} 通过, {len(failed)} 失败")
if failed:
    sys.exit(1)
print("全部通过")
