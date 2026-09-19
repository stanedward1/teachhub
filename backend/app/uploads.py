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
