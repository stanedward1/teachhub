"""通用文件上传业务逻辑（B1 分层：自 routers/uploads.py 下沉，行为完全不变）。"""
import os
import uuid

from fastapi import HTTPException, UploadFile

from app.config import settings
from app.utils import safe_filename

# 分块读取，避免大文件一次性读入内存
_CHUNK_SIZE = 1024 * 1024  # 1MB


def upload_file(file: UploadFile) -> dict:
    """通用文件上传：校验扩展名白名单与大小上限后落盘。"""
    original = file.filename or "file"
    ext = os.path.splitext(original)[1].lower()

    if ext not in settings.ALLOWED_UPLOAD_EXTS:
        allowed = "、".join(sorted(settings.ALLOWED_UPLOAD_EXTS))
        raise HTTPException(status_code=400, detail=f"不支持的文件类型 {ext or '(无扩展名)'}，仅支持：{allowed}")

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
        if os.path.exists(dest):
            os.remove(dest)
        raise

    return {
        "url": f"/uploads/{name}",
        "filepath": name,
        "filename": original,
        "size": size,
    }
