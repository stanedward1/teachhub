"""试卷（文件上传管理）：查询、上传、更新、下载、删除。"""
import os
import uuid

from fastapi import Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models import Exam
from app.schemas import ExamUpdate
from app.config import settings
from app.routers.workbench._common import (
    dep,
    get_db,
    get_current_user,
    new_router,
    audit,
    to_dict,
)
from app.utils import safe_filename

router = new_router("试卷")


@router.get("/exams")
def list_exams(keyword: str = "", _=Depends(dep), db: Session = Depends(get_db)):
    q = db.query(Exam)
    if keyword:
        q = q.filter(Exam.title.contains(keyword))
    rows = q.order_by(Exam.id.desc()).all()
    return {"items": [to_dict(x) for x in rows], "total": len(rows)}


@router.post("/exams/upload")
def upload_exam(
    title: str = "未命名试卷",
    exam_type: str = "单元测验",
    file: UploadFile = File(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传试卷文件：支持 .docx / .pdf / .doc 等格式。"""
    if not file:
        raise HTTPException(status_code=400, detail="请选择试卷文件")

    original = file.filename or "exam"
    ext = os.path.splitext(original)[1].lower()
    allowed = {".pdf", ".doc", ".docx"}
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"仅支持 PDF/Word 格式，当前文件类型：{ext}")

    name = safe_filename(os.path.splitext(original)[0]) + "_" + uuid.uuid4().hex[:8] + ext
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    dest = os.path.join(settings.UPLOAD_DIR, name)

    size = 0
    chunk_size = 1024 * 1024
    try:
        with open(dest, "wb") as f:
            while True:
                chunk = file.file.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > settings.MAX_UPLOAD_SIZE:
                    f.close()
                    os.remove(dest)
                    raise HTTPException(status_code=413, detail=f"文件过大，最大 {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB")
                f.write(chunk)
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(dest):
            os.remove(dest)
        raise

    x = Exam(
        title=title.strip() or "未命名试卷",
        exam_type=exam_type,
        filename=original,
        filepath=name,
        filesize=size,
        filetype=ext,
    )
    db.add(x)
    audit(db, user, "upload_exam", target=f"试卷上传-{original}")
    db.commit()
    db.refresh(x)
    return to_dict(x)


@router.put("/exams/{exam_id}")
def update_exam(exam_id: int, payload: ExamUpdate, user=Depends(dep), db: Session = Depends(get_db)):
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


@router.get("/exams/{exam_id}/download")
def download_exam(exam_id: int, _=Depends(dep), db: Session = Depends(get_db)):
    x = db.get(Exam, exam_id)
    if not x or not x.filepath:
        raise HTTPException(status_code=404, detail="文件不存在")
    file_path = os.path.join(settings.UPLOAD_DIR, x.filepath)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path, filename=x.filename or x.filepath, media_type="application/octet-stream")


@router.delete("/exams/{exam_id}")
def delete_exam(exam_id: int, user=Depends(dep), db: Session = Depends(get_db)):
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
