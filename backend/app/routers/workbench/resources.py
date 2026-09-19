"""教学资源：查询、增删（薄路由，逻辑见 app/services/workbench/resources_service.py）。"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.routers.workbench._common import dep, get_db, new_router
from app.schemas import ResourceCreate
from app.services.workbench import resources_service

router = new_router("教学资源")


@router.get("/resources")
def list_resources(keyword: str = "", _=Depends(dep), db: Session = Depends(get_db)):
    return resources_service.list_resources(db, keyword=keyword)


@router.post("/resources")
def create_resource(payload: ResourceCreate, user=Depends(dep), db: Session = Depends(get_db)):
    return resources_service.create_resource(db, user, payload)


@router.delete("/resources/{resource_id}")
def delete_resource(resource_id: int, user=Depends(dep), db: Session = Depends(get_db)):
    return resources_service.delete_resource(db, user, resource_id)
