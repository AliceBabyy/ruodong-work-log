"""登录态下所有页面渲染 smoke 测试（admin 账号，8010 测试实例）。"""
import http.cookiejar
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj), NoRedirect())
BASE = "http://127.0.0.1:8010"


def req(path, method="GET", data=None, follow=False):
    body = None
    headers = {}
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        resp = opener.open(r, timeout=10)
        return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if not follow and e.code in (301, 302, 303, 307, 308):
            return e.code, ""
        return e.code, e.read().decode("utf-8", "replace")


# 登录 admin
s, b = req("/login", "POST", {"username": "admin", "password": "admin123456", "next": ""})
assert s == 303, f"admin login failed: {s}"

today = date.today()
pages = [
    ("/", 200),
    ("/week", 303),            # 无日期参数 -> 重定向到本周
    (f"/week/{today.isoformat()}", 200),
    ("/todos", 200),
    (f"/day/{today.isoformat()}/timeline", 200),
    (f"/day/{today.isoformat()}/work", 200),
    (f"/day/{today.isoformat()}/study", 200),
    (f"/day/{today.isoformat()}/rest", 200),
    (f"/day/{today.isoformat()}/todos", 200),
    ("/work/add", 200),
    ("/study/add", 200),
    ("/rest/add", 200),
    ("/login", 303),           # 已登录访问登录页 -> 重定向回站内
    ("/register", 303),        # 已登录访问注册页 -> 重定向回站内
]
ok = True
for p, expect in pages:
    s, b = req(p)
    status_ok = s == expect
    has_error = "Traceback" in b or "Internal Server Error" in b
    mark = "PASS" if (status_ok and not has_error) else "FAIL"
    if mark == "FAIL":
        ok = False
    print(f"  {mark}  {p}  -> {s} (期望 {expect})" + ("  [含错误页]" if has_error else ""))

print()
print("页面 smoke 测试:", "全部通过" if ok else "存在失败")
sys.exit(0 if ok else 1)
