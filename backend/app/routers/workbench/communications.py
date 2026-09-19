"""家校沟通记录：查询、增删（薄路由，逻辑见 app/services/workbench/communications_service.py）。"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.routers.workbench._common import get_current_user, get_db, new_router
from app.schemas import CommunicationCreate, CommunicationOut
from app.services.workbench import communications_service

router = new_router("家校沟通")


@router.get("/communications")
def list_communications(page: int = 1, page_size: int = 20, student_id: int | None = None, class_id: int | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return communications_service.list_communications(
        db, user, page=page, page_size=page_size, student_id=student_id, class_id=class_id
    )


@router.post("/communications", response_model=CommunicationOut)
def create_communication(payload: CommunicationCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return communications_service.create_communication(db, user, payload)


@router.delete("/communications/{communication_id}")
def delete_communication(communication_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return communications_service.delete_communication(db, user, communication_id)
