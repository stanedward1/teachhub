"""上传文件落盘的公共逻辑。

背景
----
通用上传（``services/uploads_service.upload_file``）与试卷上传
（``services/workbench/exams_service.upload_exam``）原本各自实现了一套**完全相同**的
流程：扩展名白名单校验 → ``safe_filename`` + uuid 命名 → 分块读取 → 大小上限判定 →
失败时清理半成品文件。两者仅白名单与错误文案不同，属于复制粘贴式重复，
任一侧修 bug（如文件头校验）都容易漏改另一侧。

本模块把落盘过程收敛为单一实现，两处通过参数表达差异（白名单、错误文案）。
"""
from __future__ import annotations

import os
import uuid
import zipfile
from io import BytesIO
from typing import Callable, Iterable

from fastapi import HTTPException, UploadFile

from app.config import settings
from app.utils import safe_filename

# 分块读取，避免大文件一次性读入内存
_CHUNK_SIZE = 1024 * 1024  # 1MB


def save_upload(
    file: UploadFile,
    *,
    allowed_exts: Iterable[str],
    type_error_detail: str | Callable[[str], str] | None = None,
    default_name: str = "file",
) -> dict:
    """校验扩展名与大小上限后把上传文件分块落盘。

    Args:
        file: FastAPI 的 ``UploadFile``。
        allowed_exts: 允许的扩展名集合（含前导点、小写，如 ``{".pdf", ".docx"}``）。
        type_error_detail: 扩展名不在白名单时的 400 错误文案。
            - ``None``：自动生成「不支持的文件类型 X，仅支持：...」；
            - ``str``：固定文案；
            - ``Callable[[str], str]``：按实际扩展名生成文案。
        default_name: ``file.filename`` 为空时使用的默认文件名。

    Returns:
        ``{"url": 访问路径, "filepath": 落盘文件名, "filename": 原始文件名, "size": 字节数}``

    Raises:
        HTTPException: 400（类型不允许）/ 413（超过 ``settings.MAX_UPLOAD_SIZE``）。
    """
    exts = set(allowed_exts)
    original = file.filename or default_name
    ext = os.path.splitext(original)[1].lower()

    if ext not in exts:
        if callable(type_error_detail):
            detail = type_error_detail(ext)
        elif type_error_detail is not None:
            detail = type_error_detail
        else:
            allowed = "、".join(sorted(exts))
            detail = f"不支持的文件类型 {ext or '(无扩展名)'}，仅支持：{allowed}"
        raise HTTPException(status_code=400, detail=detail)

    name = safe_filename(os.path.splitext(original)[0]) + "_" + uuid.uuid4().hex[:8] + ext

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    dest = os.path.join(settings.UPLOAD_DIR, name)

    size = 0
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = file.file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.MAX_UPLOAD_SIZE:
                    # 超限：关闭句柄并删除半成品，避免残留垃圾文件
                    f.close()
                    os.remove(dest)
                    raise HTTPException(
                        status_code=413,
                        detail=f"文件过大，最大允许 {settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception:
        # 落盘过程中的任何异常都要清掉半成品文件
        if os.path.exists(dest):
            os.remove(dest)
        raise

    return {
        "url": f"/uploads/{name}",
        "filepath": name,
        "filename": original,
        "size": size,
    }


# ---------------- 压缩容器的解压体积护栏（zip bomb） ----------------
# `.docx` / `.xlsx` 都是 zip 容器：0.2MB 的包可以声明 200MB 的解压体积。2026-11-17 实测
# 0.2MB docx → 解压 200MB 被 python-docx **完整读入内存**（1.8s，全程无拒绝）。批改与
# API 跑在同一个进程里，一次 OOM 会带走整个服务（含其他租户），所以必须在**解析之前**
# 按下表拦掉（`docs/REVIEW-2026-11-17-OPT.md` SEC-05）。
#
# 两个判据缺一不可：
# - 绝对上限：解压总量 ≤ `ZIP_MAX_UNCOMPRESSED_BYTES`；
# - 解压比：总量超过 `ZIP_RATIO_MIN_BYTES` 后，比值 > `ZIP_MAX_RATIO` 视为异常。
#   下限是必需的：压缩比高本身不是问题（纯 XML 的 docx 轻松 10×~30×），
#   1KB 的包解出 200KB 完全正常；只在大体积时比值才有判别力。
ZIP_MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
ZIP_MAX_RATIO = 100
ZIP_RATIO_MIN_BYTES = 16 * 1024 * 1024


def zip_expansion_reason(src) -> str | None:
    """检查 zip 容器的解压体积：安全返回 ``None``，否则返回中文原因。**不抛异常**。

    Args:
        src: 磁盘路径，或已经读进内存的 ``bytes``（导入接口用后者，避免二次读盘）。

    ⚠️ 只读 zip 中央目录里的 ``file_size`` / ``compress_size``，**一个条目都不解压** ——
    护栏本身不能成为新的内存消耗点（这也是「先查目录、再交给解析库」的原因）。
    """
    try:
        handle = BytesIO(src) if isinstance(src, (bytes, bytearray)) else src
        archive = zipfile.ZipFile(handle)
    except zipfile.BadZipFile:
        return "文件不是有效的压缩包（可能已损坏）"
    except OSError:
        return "无法读取文件"
    try:
        infos = archive.infolist()
        total = sum(i.file_size for i in infos)
        packed = sum(i.compress_size for i in infos)
    finally:
        archive.close()

    if total > ZIP_MAX_UNCOMPRESSED_BYTES:
        return (
            f"解压后体积过大（{total // (1024 * 1024)}MB，"
            f"上限 {ZIP_MAX_UNCOMPRESSED_BYTES // (1024 * 1024)}MB）"
        )
    if total > ZIP_RATIO_MIN_BYTES and packed > 0 and total / packed > ZIP_MAX_RATIO:
        return f"解压比异常（约 {total // packed}×，上限 {ZIP_MAX_RATIO}×），疑似压缩炸弹"
    return None


# ---------------- 相对路径解析（唯一安全口径） ----------------
def resolve_upload_path(rel: str) -> str:
    """把「上传目录内的相对路径」解析成磁盘绝对路径，并**强制约束在上传目录内**。

    这是全项目**唯一**的「相对 filepath → 磁盘路径」实现。历史上
    `homework_service._remove_upload_files` 与 `ai_attachments.absolute_path` 各写了一份
    `os.path.join(settings.UPLOAD_DIR, p.lstrip("/")...)` —— `lstrip("/")` 只挡前导斜杠，
    对 `..` 毫无防护，于是请求体里的 `../../x` 会让删除/读取**逃出上传目录**
    （学生即可删/读服务器任意文件，见 `docs/REVIEW-2026-09-25-code-audit.md` P0-A）。
    两份拷贝只修一处必漏，故收口到这里。

    实现要点（缺一不可）：
    - `os.path.join(base, "/abs")` 会**直接顶掉** base，Windows 下 `C:x` 同理 ⇒ 先拒绝；
    - `os.path.realpath` 归一化 `..`；
    - 前缀比较必须用 `base + os.sep`，否则 `/uploads_evil` 会被误判为在 `/uploads` 内；
    - 🔴 **不能只靠 realpath 防符号链接**：实测（Windows + 本机文件系统）`os.path.realpath`
      对链接**不解除**，`os.symlink` 甚至可能造出非重解析点。故再显式遍历路径链，
      任一环节是 symlink 即拒绝 —— 链接可以把「上传目录内的名字」指向目录之外。

    Args:
        rel: 相对路径，如 ``a.txt``、``uploads/a.txt``、``not/exist/missing.pdf``。

    Returns:
        磁盘绝对路径（可能指向尚不存在的文件，由调用方判存在）。

    Raises:
        ValueError: 路径为空、含 NUL、绝对路径 / 带盘符、或解析后逃出上传目录。
    """
    raw = "" if rel is None else str(rel)
    if not raw.strip():
        raise ValueError("文件路径不能为空")
    raw = raw.strip()
    if "\x00" in raw:
        raise ValueError("文件路径非法")
    base = os.path.realpath(settings.UPLOAD_DIR)
    # 统一分隔符后再判绝对路径，避免 `..\x` 或 `/x` 在 Windows 上漏判
    candidate = raw.replace("\\", os.sep).replace("/", os.sep)
    if os.path.isabs(candidate) or os.path.splitdrive(candidate)[0]:
        raise ValueError("文件路径非法")
    full = os.path.realpath(os.path.join(base, candidate))
    if full != base and not full.startswith(base + os.sep):
        raise ValueError("文件路径非法")
    # 显式 symlink 检查（见 docstring：realpath 在部分平台不解链接）
    cur = base
    for part in os.path.relpath(full, base).split(os.sep):
        if part in ("", "."):
            continue
        cur = os.path.join(cur, part)
        if os.path.islink(cur):
            raise ValueError("文件路径非法")
    return full


def ensure_upload_path(rel: str) -> str:
    """`resolve_upload_path` 的 HTTP 版本：非法路径 → **400**。

    供「请求体里带 filepath」的写接口在服务层直接调用，避免把穿越路径落库。
    """
    try:
        return resolve_upload_path(rel)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="文件路径非法：只能引用上传目录内的文件"
        )

