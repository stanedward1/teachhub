"""教学资源业务逻辑：查询、增删。"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Resource
from app.schemas import ResourceCreate
from app.services.workbench._common import audit, to_dict


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
    x = Resource(
        name=name,
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
