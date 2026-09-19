"""数据导入：学生/成绩批量导入 + 模板下载 + 导入历史（薄路由，逻辑见 app/services/workbench/imports_service.py）。"""
from fastapi import Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.routers.workbench._common import dep, get_current_user, get_db, new_router
from app.services.workbench import imports_service

router = new_router("数据导入")


@router.get("/students/template")
def download_student_template(_=Depends(dep)):
    return imports_service.download_student_template()


@router.post("/students/import")
def import_students(
    file: UploadFile = File(...),
    user=Depends(dep),
    db: Session = Depends(get_db),
):
    return imports_service.import_students(db, user, file)


@router.get("/import-history")
def list_import_history(
    import_type: str = "",
    page: int = 1,
    page_size: int = 20,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return imports_service.list_import_history(
        db, user, import_type=import_type, page=page, page_size=page_size
    )
