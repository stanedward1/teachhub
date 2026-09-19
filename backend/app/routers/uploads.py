"""文件上传接口（路由层：仅声明路径 / 依赖注入 / 参数解析 / 调用 service / 返回）。"""
from fastapi import APIRouter, Depends, File, UploadFile

from app.deps import get_current_user
from app.services import uploads_service

router = APIRouter(prefix="/api/uploads", tags=["文件上传"])


@router.post("")
def upload_file(
    file: UploadFile = File(...),
    _=Depends(get_current_user),
):
    """通用文件上传：校验扩展名白名单与大小上限后落盘。"""
    return uploads_service.upload_file(file)
