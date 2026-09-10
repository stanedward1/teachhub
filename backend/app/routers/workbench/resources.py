"""教学资源：查询、增删。"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.models import Resource
from app.schemas import ResourceCreate
from app.routers.workbench._common import (
    dep,
    get_db,
    new_router,
    audit,
    to_dict,
)

router = new_router("教学资源")


@router.get("/resources")
def list_resources(keyword: str = "", _=Depends(dep), db: Session = Depends(get_db)):
    q = db.query(Resource)
    if keyword:
        q = q.filter(Resource.name.contains(keyword))
    rows = q.order_by(Resource.id.desc()).all()
    return {"items": [to_dict(x) for x in rows], "total": len(rows)}


@router.post("/resources")
def create_resource(payload: ResourceCreate, user=Depends(dep), db: Session = Depends(get_db)):
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


@router.delete("/resources/{resource_id}")
def delete_resource(resource_id: int, user=Depends(dep), db: Session = Depends(get_db)):
    x = db.get(Resource, resource_id)
    if not x:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(x)
    audit(db, user, "delete_resource", target=f"资源#{resource_id}")
    db.commit()
    return {"ok": True}
