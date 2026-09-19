"""试卷（文件上传管理）业务逻辑：查询、上传、更新、下载、删除。"""
import os

from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Exam
from app.schemas import ExamUpdate
from app.services.workbench._common import audit, to_dict
from app.uploads import save_upload

# 试卷允许的文档格式
_EXAM_EXTS = {".pdf", ".doc", ".docx"}


def list_exams(db: Session, keyword: str = "") -> dict:
    """试卷列表（标题关键词过滤），非分页。"""
    q = db.query(Exam)
    if keyword:
        q = q.filter(Exam.title.contains(keyword))
    rows = q.order_by(Exam.id.desc()).all()
    return {"items": [to_dict(x) for x in rows], "total": len(rows)}


def upload_exam(db: Session, user, title: str = "未命名试卷", exam_type: str = "单元测验", file=None) -> dict:
    """上传试卷文件：支持 .docx / .pdf / .doc 等格式。"""
    if not file:
        raise HTTPException(status_code=400, detail="请选择试卷文件")

    original = file.filename or "exam"
    ext = os.path.splitext(original)[1].lower()

    # 落盘过程与通用上传共用 app.uploads.save_upload（扩展名白名单与错误文案在此表达差异）
    saved = save_upload(
        file,
        allowed_exts=_EXAM_EXTS,
        type_error_detail=lambda e: f"仅支持 PDF/Word 格式，当前文件类型：{e}",
        default_name="exam",
    )

    x = Exam(
        title=title.strip() or "未命名试卷",
        exam_type=exam_type,
        filename=saved["filename"],
        filepath=saved["filepath"],
        filesize=saved["size"],
        filetype=ext,
    )
    db.add(x)
    audit(db, user, "upload_exam", target=f"试卷上传-{original}")
    db.commit()
    db.refresh(x)
    return to_dict(x)


def update_exam(db: Session, user, exam_id: int, payload: ExamUpdate) -> dict:
    """更新试卷标题 / 类型。"""
    x = db.get(Exam, exam_id)
    if not x:
        raise HTTPException(status_code=404, detail="试卷不存在")
    data = payload.model_dump(exclude_unset=True)
    for f in ("title", "exam_type"):
        if f in data and data[f] is not None:
            setattr(x, f, data[f])
    audit(db, user, "update_exam", target=f"试卷#{exam_id}")
    db.commit()
    db.refresh(x)
    return to_dict(x)


def download_exam(db: Session, exam_id: int) -> FileResponse:
    """下载试卷文件。"""
    x = db.get(Exam, exam_id)
    if not x or not x.filepath:
        raise HTTPException(status_code=404, detail="文件不存在")
    file_path = os.path.join(settings.UPLOAD_DIR, x.filepath)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path, filename=x.filename or x.filepath, media_type="application/octet-stream")


def delete_exam(db: Session, user, exam_id: int) -> dict:
    """删除试卷及其磁盘文件。"""
    x = db.get(Exam, exam_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    if x.filepath:
        fp = os.path.join(settings.UPLOAD_DIR, x.filepath)
        if os.path.exists(fp):
            os.remove(fp)
    db.delete(x)
    audit(db, user, "delete_exam", target=f"试卷#{exam_id}")
    db.commit()
    return {"ok": True}
