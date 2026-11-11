"""`/uploads` 静态目录的**受控**挂载（RBT-78）。

为什么不能直接 ``app.mount("/uploads", StaticFiles(...))``
----------------------------------------------------------
三处事实叠加成一条完整攻击链：

1. 上传白名单包含 ``.html`` / ``.js`` / ``.css``（`config.ALLOWED_UPLOAD_EXTS`）——
   这是**功能需求**，编程 / 网页设计课的作业就是这几种格式，不能拒收；
2. 上传接口只要求登录，学生账号即可上传；
3. 原来的挂载让静态文件按扩展名推断 ``Content-Type`` 后**同源直出**，且不带任何下载头。

于是学生上传一个 ``evil.html``，把 ``http://<域名>/uploads/evil.html`` 发给老师/管理员，
对方点开就在**同源**执行任意 JS ⇒ 读 ``localStorage`` 里的 refresh token ⇒ 长期接管账号。

修法边界（两条红线，勿回退）
----------------------------
* **不得**以「拒收 .html/.js/.css」来结案 —— 会砍掉网页/编程课的作业提交；
* **不得**改名落盘（如把 ``.html`` 存成 ``.html.txt``）—— 学生下载后打不开，且
  `resolve_upload_path` 的路径口径与历史数据都会错位。

因此正确的收口是**出口侧**：对「浏览器会主动渲染/执行」的类型强制 ``attachment``，
再叠加 ``nosniff`` 与 ``CSP: sandbox`` 双层防御。图片/PDF/Office 文档仍照常内联预览。

为什么**不**把 ``Content-Type`` 改成 ``application/octet-stream``
---------------------------------------------------------------
R8 报告的建议里提到过这个选项，这里刻意不用：`attachment` 已经让浏览器走下载，
而万一某个客户端忽略它（部分 WebView / 内置预览器），真正兜底的是
``CSP: sandbox`` —— 文档落在**不透明源**里，读不到本站 localStorage、也发不出带凭证的
同源请求。反过来把类型改成 octet-stream 会让 ``curl -I`` / 排障时看到的类型全是假的
（「作业是 pdf 还是 html」得去翻扩展名），而它挡不住的东西 CSP 已经挡住了。
若将来要上「独立子域托管上传目录」，那才是根治，届时本模块可整体退场。

⚠️ ``nosniff`` **单独用不足以修 RBT-78**：它只阻止 MIME 嗅探，而 ``.html`` 的
``Content-Type`` 本来就是 ``text/html``，浏览器会正常渲染。必须同时给
``Content-Disposition: attachment``（见 `docs/REVIEW-2026-11-06-R8-robustness.md`）。
"""
from __future__ import annotations

import mimetypes
import os
import re
from urllib.parse import quote

from starlette.responses import Response
from starlette.staticfiles import StaticFiles

# 浏览器会主动渲染 / 执行、且在同源下能读到 localStorage 的类型。
_FORCE_DOWNLOAD_MEDIA_TYPES = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
        "image/svg+xml",
        "text/javascript",
        "application/javascript",
        "application/ecmascript",
        "text/ecmascript",
        "text/css",
        "text/xml",
        "application/xml",
        "application/rss+xml",
        "application/atom+xml",
    }
)

# 扩展名兜底：部分平台的 mimetypes 表缺项（如容器里没装 media types 时返回 None），
# 只靠 media type 判断会漏掉 .html。两份清单必须同步维护。
_FORCE_DOWNLOAD_EXTS = frozenset(
    {
        ".html",
        ".htm",
        ".xhtml",
        ".shtml",
        ".svg",
        ".js",
        ".mjs",
        ".cjs",
        ".css",
        ".xml",
        ".xsl",
        ".xslt",
        ".htc",
        ".mhtml",
        ".mht",
    }
)


def is_renderable(path: str) -> bool:
    """该文件是否会被浏览器当作页面 / 脚本 / 样式渲染（→ 必须强制下载）。"""
    ext = os.path.splitext(path)[1].lower()
    if ext in _FORCE_DOWNLOAD_EXTS:
        return True
    media_type, _encoding = mimetypes.guess_type(path)
    return (media_type or "").lower() in _FORCE_DOWNLOAD_MEDIA_TYPES


def content_disposition(filename: str) -> str:
    """构造 ``attachment`` 头，同时兼容 ASCII 与中文文件名。

    ``filename`` 参数用 ASCII 兜底（老客户端不认 ``filename*``），``filename*`` 按
    RFC 5987 用 UTF-8 百分号编码 —— 只给前者会让中文名变成一串下划线。
    """
    ascii_name = re.sub(r"[^\x20-\x7e]", "_", filename).replace('"', "_").replace("\\", "_")
    if not ascii_name.strip(". _"):
        ascii_name = "download"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"


class SafeUploadsStaticFiles(StaticFiles):
    """``StaticFiles`` + 出口侧安全头。其余行为（Range / ETag / 304）保持不变。

    覆盖点选 ``file_response`` 而不是 ``get_response``：前者拿得到**磁盘全路径**
    （能判扩展名），且 404 / 405 等错误分支仍走父类，无需重复处理。
    """

    def file_response(self, full_path, stat_result, scope, status_code=200) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        # 所有上传文件都禁嗅探：不让 .txt / .c 被当成 HTML 执行（成本为零）
        response.headers["X-Content-Type-Options"] = "nosniff"
        if is_renderable(str(full_path)):
            response.headers["Content-Disposition"] = content_disposition(
                os.path.basename(str(full_path))
            )
            # 双层防御：即使某个客户端（如内置预览器）忽略 attachment，脚本也落在
            # **不透明源**里执行，拿不到本站的 localStorage / cookie。
            response.headers["Content-Security-Policy"] = "sandbox"
        return response
