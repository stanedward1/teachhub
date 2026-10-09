"""通用文件上传业务逻辑（B1 分层：自 routers/uploads.py 下沉，行为完全不变）。"""
import os
import uuid

from fastapi import HTTPException, UploadFile

from app.cleanup import delete_avatar_file
from app.config import settings
from app.uploads import save_upload

# 头像上传的常量（自 routers/auth.py 下沉）：2MB 上限 + 图片扩展名白名单。
_AVATAR_MAX_SIZE = 2 * 1024 * 1024  # 2MB
_AVATAR_ALLOWED = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def upload_file(file: UploadFile) -> dict:
    """通用文件上传：校验扩展名白名单与大小上限后落盘。

    落盘过程（扩展名校验 / uuid 命名 / 分块写入 / 超限清理）由
    :func:`app.uploads.save_upload` 统一实现，与试卷上传共用。
    """
    return save_upload(file, allowed_exts=settings.ALLOWED_UPLOAD_EXTS, default_name="file")


def save_avatar(file: UploadFile, user_id: int, old_path: str | None = None) -> str:
    """学生 / 教师头像上传：校验扩展名与大小上限后落盘，并清理旧头像。

    自 ``routers/auth.py`` 的 ``upload_avatar`` 下沉，行为逐字节等价
    （400/413 状态码与文案、uuid 命名、超限删半成品、删旧头像均保持不变）。

    Args:
        file: FastAPI 的 ``UploadFile``。
        user_id: 上传者 id（用于新头像文件名 ``avatar_{user_id}_{8hex}{ext}``）。
        old_path: 上传者当前头像 URL（形如 ``/uploads/avatars/xxx.png``）；
            新头像落盘成功后清理对应旧文件，无旧头像传 ``None``。

    Returns:
        新头像的站内访问路径（``/uploads/avatars/<name>``），由调用方落库。

    Raises:
        HTTPException: 400（扩展名不在图片白名单）/ 413（超过 2MB）。
    """
    original = file.filename or "avatar"
    ext = os.path.splitext(original)[1].lower()
    if ext not in _AVATAR_ALLOWED:
        raise HTTPException(
            status_code=400, detail=f"仅支持图片格式：{'、'.join(sorted(_AVATAR_ALLOWED))}"
        )

    name = f"avatar_{user_id}_{uuid.uuid4().hex[:8]}{ext}"
    os.makedirs(settings.AVATAR_DIR, exist_ok=True)
    dest = os.path.join(settings.AVATAR_DIR, name)

    size = 0
    chunk_size = 1024 * 1024
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = file.file.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > _AVATAR_MAX_SIZE:
                    # 超限：关闭句柄并删除半成品，避免残留垃圾文件
                    f.close()
                    os.remove(dest)
                    raise HTTPException(
                        status_code=413,
                        detail=f"头像文件不能超过 {_AVATAR_MAX_SIZE // (1024 * 1024)}MB",
                    )
                f.write(chunk)
    except HTTPException:
        raise
    except Exception:
        # 落盘过程中的任何异常都要清掉半成品文件
        if os.path.exists(dest):
            os.remove(dest)
        raise

    # 删除旧头像文件（沿用 cleanup 的既有实现：不存在则静默跳过）
    if old_path:
        delete_avatar_file(old_path)

    return f"/uploads/avatars/{name}"
