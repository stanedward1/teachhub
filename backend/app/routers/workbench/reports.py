"""班级周报：周数据汇总 + 周报增删查（薄路由，逻辑见 app/services/workbench/reports_service.py）。"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.routers.workbench._common import dep, get_current_user, get_db, new_router
from app.schemas import ReportSave
from app.services.workbench import reports_service

router = new_router("班级周报")


@router.get("/reports/weekly-data")
def get_weekly_data(class_id: int, week_start: str = "", week_end: str = "", user=Depends(get_current_user), db: Session = Depends(get_db)):
    return reports_service.get_weekly_data(db, user, class_id, week_start=week_start, week_end=week_end)


@router.get("/reports")
def list_reports(class_id: int | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return reports_service.list_reports(db, user, class_id=class_id)


@router.post("/reports")
def save_report(payload: ReportSave, user=Depends(dep), db: Session = Depends(get_db)):
    return reports_service.save_report(db, user, payload)


@router.delete("/reports/{report_id}")
def delete_report(report_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return reports_service.delete_report(db, user, report_id)
