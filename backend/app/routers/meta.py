"""公共元数据接口（路由层：仅声明路径 / 依赖注入 / 参数解析 / 调用 service / 返回）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import meta_service

router = APIRouter(prefix="/api/meta", tags=["公共"])


@router.get("/classes")
def class_options(school_id: int | None = None, db: Session = Depends(get_db)):
    """班级下拉选项（登录/注册时使用，无需登录）。仅返回未毕业班级。

    传入 school_id 时只返回该校班级（多租户下学生登录页按学校级联）。
    🔴 未传 school_id 时返回空列表：本端点无需登录，不做限制会匿名暴露全部学校的
    班级信息；调用方（登录/注册页）必须先选定学校再拉取。
    """
    return meta_service.class_options(db, school_id)


@router.get("/practice")
def practice_data():
    return meta_service.practice_data()
