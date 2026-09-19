"""试卷（文件上传管理）：查询、上传、更新、下载、删除（薄路由，逻辑见 app/services/workbench/exams_service.py）。"""
from fastapi import Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.routers.workbench._common import dep, get_current_user, get_db, new_router
from app.schemas import ExamUpdate
from app.services.workbench import exams_service

router = new_router("试卷")


@router.get("/exams")
def list_exams(keyword: str = "", _=Depends(dep), db: Session = Depends(get_db)):
    return exams_service.list_exams(db, keyword=keyword)


@router.post("/exams/upload")
def upload_exam(
    title: str = "未命名试卷",
    exam_type: str = "单元测验",
    file: UploadFile = File(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return exams_service.upload_exam(db, user, title=title, exam_type=exam_type, file=file)


@router.put("/exams/{exam_id}")
def update_exam(exam_id: int, payload: ExamUpdate, user=Depends(dep), db: Session = Depends(get_db)):
    return exams_service.update_exam(db, user, exam_id, payload)


@router.get("/exams/{exam_id}/download")
def download_exam(exam_id: int, _=Depends(dep), db: Session = Depends(get_db)):
    return exams_service.download_exam(db, exam_id)


@router.delete("/exams/{exam_id}")
def delete_exam(exam_id: int, user=Depends(dep), db: Session = Depends(get_db)):
    return exams_service.delete_exam(db, user, exam_id)
