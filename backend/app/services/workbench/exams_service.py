"""试卷（文件上传管理）业务逻辑：查询、上传、更新、下载、删除。"""
import os

from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models import Exam
from app.schemas import ExamUpdate
from app.services.workbench._common import (
    audit,
    resolve_school_id_for_schools_scope,
    to_dict,
)
from app.uploads import resolve_upload_path, save_upload

# 试卷允许的文档格式
_EXAM_EXTS = {".pdf", ".doc", ".docx"}


def list_exams(db: Session, keyword: str = "") -> dict:
    """试卷列表（标题关键词过滤），非分页。"""
    q = db.query(Exam)
    if keyword:
        q = q.filter(Exam.title.contains(keyword))
    rows = q.order_by(Exam.id.desc()).all()
    return {"items": [to_dict(x) for x in rows], "total": len(rows)}


def upload_exam(
    db: Session,
    user,
    title: str = "未命名试卷",
    exam_type: str = "单元测验",
    file=None,
    school_id: int | None = None,
) -> dict:
    """上传试卷文件：支持 .docx / .pdf / .doc 等格式。"""
    if not file:
        raise HTTPException(status_code=400, detail="请选择试卷文件")

    # 先解析归属学校（超管必须显式指定）——放在落盘之前，避免校验失败却已把文件写入磁盘。
    # 试卷是学校级实体、无父资源可继承：超管需显式指定，教师/校管取自身 school_id。
    resolved_school_id = resolve_school_id_for_schools_scope(db, user, school_id)

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
        school_id=resolved_school_id,
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
    """下载试卷文件。

    🔴 `filepath` 必须经 `uploads.resolve_upload_path` 归一化并**约束在上传目录内**。
    该值来自上传接口（服务端生成），当前**没有**客户端注入入口，但历史上这里是
    `os.path.join(settings.UPLOAD_DIR, x.filepath)` —— 与出事的 P0-A 是**同一个危险模式**，
    一旦将来某个写接口能改到 `Exam.filepath`（或库中已有异常行），就会退化成任意文件读取。
    按「同一模式统一收口」的原则，这里一并改用唯一的安全实现
    （见 docs/REVIEW-2026-09-25-code-audit.md P2-A）。
    """
    x = db.get(Exam, exam_id)
    if not x or not x.filepath:
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        file_path = resolve_upload_path(x.filepath)
    except ValueError:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path, filename=x.filename or x.filepath, media_type="application/octet-stream")


def delete_exam(db: Session, user, exam_id: int) -> dict:
    """删除试卷及其磁盘文件。"""
    x = db.get(Exam, exam_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    if x.filepath:
        # 同上：删除是**破坏性**操作，非法路径一律跳过（宁可留下垃圾文件，不可删错）
        try:
            fp = resolve_upload_path(x.filepath)
        except ValueError:
            fp = None
        if fp and os.path.isfile(fp):
            os.remove(fp)
    db.delete(x)
    audit(db, user, "delete_exam", target=f"试卷#{exam_id}")
    db.commit()
    return {"ok": True}
