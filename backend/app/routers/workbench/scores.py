"""成绩：查询、分析、增删改、导入导出（薄路由，逻辑见 app/services/workbench/scores_service.py）。"""
from fastapi import Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.routers.workbench._common import dep, get_current_user, get_db, new_router
from app.schemas import ScoreCreate, ScoreOut, ScoreUpdate
from app.services.workbench import scores_service

router = new_router("成绩")


@router.get("/scores")
def list_scores(
    page: int = 1,
    page_size: int = 20,
    student_id: int | None = None,
    class_id: int | None = None,
    subject: str = "",
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return scores_service.list_scores(
        db, user, page=page, page_size=page_size, student_id=student_id, class_id=class_id, subject=subject
    )


@router.get("/scores/analysis")
def score_analysis(
    class_id: int | None = None,
    student_id: int | None = None,
    subject: str = "",
    exam_name: str = "",
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return scores_service.score_analysis(
        db, user, class_id=class_id, student_id=student_id, subject=subject, exam_name=exam_name
    )


@router.post("/scores", response_model=ScoreOut)
def create_score(payload: ScoreCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return scores_service.create_score(db, user, payload)


@router.put("/scores/{score_id}", response_model=ScoreOut)
def update_score(score_id: int, payload: ScoreUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return scores_service.update_score(db, user, score_id, payload)


@router.delete("/scores/{score_id}")
def delete_score(score_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return scores_service.delete_score(db, user, score_id)


@router.get("/scores/export")
def export_scores(student_id: int | None = None, class_id: int | None = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    return scores_service.export_scores(db, user, student_id=student_id, class_id=class_id)


@router.get("/scores/template")
def download_score_template(_=Depends(dep)):
    return scores_service.download_score_template()


@router.post("/scores/import")
def import_scores(
    file: UploadFile = File(...),
    user=Depends(dep),
    db: Session = Depends(get_db),
):
    return scores_service.import_scores(db, user, file)
