"""通用文件上传业务逻辑（B1 分层：自 routers/uploads.py 下沉，行为完全不变）。"""
from fastapi import UploadFile

from app.config import settings
from app.uploads import save_upload


def upload_file(file: UploadFile) -> dict:
    """通用文件上传：校验扩展名白名单与大小上限后落盘。

    落盘过程（扩展名校验 / uuid 命名 / 分块写入 / 超限清理）由
    :func:`app.uploads.save_upload` 统一实现，与试卷上传共用。
    """
    return save_upload(file, allowed_exts=settings.ALLOWED_UPLOAD_EXTS, default_name="file")
