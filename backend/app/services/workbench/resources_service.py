"""教学资源业务逻辑：查询、增删。"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Resource
from app.schemas import ResourceCreate
from app.services.workbench._common import (
    audit,
    resolve_school_id_for_schools_scope,
    to_dict,
)
from app.uploads import ensure_upload_path


def list_resources(db: Session, keyword: str = "") -> dict:
    """教学资源列表（关键词过滤），非分页，返回全量 + 总数。"""
    q = db.query(Resource)
    if keyword:
        q = q.filter(Resource.name.contains(keyword))
    rows = q.order_by(Resource.id.desc()).all()
    return {"items": [to_dict(x) for x in rows], "total": len(rows)}


def create_resource(db: Session, user, payload: ResourceCreate) -> dict:
    """新增教学资源。"""
    name = payload.name.strip()
    # filepath 来自请求体，落库后即为「上传目录内的相对路径」引用 ⇒ 必须走全项目唯一安全
    # 口径校验（与 homework_service._sync_attachments 一致：非法路径 → 400）。
    # 仅在非空时校验：前端允许「只填名称、不附文件」的资源（此时 filepath 为空串）。
    if payload.filepath:
        ensure_upload_path(payload.filepath)
    # 资源是学校级实体、无父资源可继承：超管必须显式指定归属学校（否则落 NULL 全租户不可见），
    # 教师/校管忽略入参、取自身 school_id（防跨校写入）。
    school_id = resolve_school_id_for_schools_scope(db, user, payload.school_id)
    x = Resource(
        name=name,
        school_id=school_id,
        category=payload.category,
        filename=payload.filename,
        filepath=payload.filepath,
    )
    db.add(x)
    audit(db, user, "create_resource", target="新增资源")
    db.commit()
    db.refresh(x)
    return to_dict(x)


def delete_resource(db: Session, user, resource_id: int) -> dict:
    """删除教学资源。"""
    x = db.get(Resource, resource_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(x)
    audit(db, user, "delete_resource", target=f"资源#{resource_id}")
    db.commit()
    return {"ok": True}
