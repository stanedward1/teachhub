"""数据导入业务逻辑：学生/成绩批量导入 + 模板下载 + 导入历史。"""
import json
from io import BytesIO

from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Classroom, ImportHistory, Student, User
from app.pagination import paginate
from app.permissions import get_student_account
from app.security import hash_password
from app.services.workbench._common import (
    get_teacher_class_ids,
    is_any_admin,
    normalize_page,
    parse_date,
    to_dict,
)
from app.services.workbench.importer import ROW_FAIL, ROW_OK, run_import

_EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _validate_student_row(row_data: dict, row_num: int) -> list[str]:
    """校验学生导入行数据，返回错误列表。"""
    errors = []
    if not row_data.get("name", "").strip():
        errors.append(f"第{row_num}行：姓名不能为空")
    if not row_data.get("student_no", "").strip():
        errors.append(f"第{row_num}行：学号不能为空")
    if not row_data.get("class_name", "").strip():
        errors.append(f"第{row_num}行：班级不能为空")
    return errors


def download_student_template() -> StreamingResponse:
    """下载学生导入模板。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "学生导入模板"
    ws.append(["学号", "姓名", "性别", "班级", "专业", "出生日期", "家长姓名", "家长电话", "学生类型"])
    ws.append(["2024001", "张三", "男", "2024级1班", "计算机", "2008-05-12", "张父", "13800000000", "通学生"])
    for col, w in enumerate([12, 10, 6, 14, 14, 12, 10, 14, 10], 1):
        ws.column_dimensions[ws.cell(1, col).column_letter].width = w
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type=_EXCEL_MIME, headers={"Content-Disposition": "attachment; filename=student_template.xlsx"})


def import_students(db: Session, user, file) -> dict:
    """批量导入学生数据。

    文件解析、行级事务、审计与导入历史由 :func:`run_import` 统一处理；
    这里只提供「解析 + 业务校验 + 写入」的单行逻辑。
    """
    if not is_any_admin(user):
        teacher_class_ids = get_teacher_class_ids(db, user.id)
    else:
        teacher_class_ids = None

    class_objs = db.query(Classroom).all()
    classrooms = {c.name: c.id for c in class_objs}
    class_school = {c.id: c.school_id for c in class_objs}
    graduated_class_ids = {c.id for c in class_objs if c.is_graduated}

    def handle_row(session: Session, row: tuple, row_num: int) -> tuple[int, list[str]]:
        data = {
            "student_no": str(row[0] or "").strip(),
            "name": str(row[1] or "").strip(),
            "gender": str(row[2] or "").strip() or "男",
            "class_name": str(row[3] or "").strip(),
            "major": str(row[4] or "").strip(),
            "birth_date": str(row[5] or "").strip(),
            "parent_name": str(row[6] or "").strip(),
            "parent_phone": str(row[7] or "").strip(),
            "student_type": str(row[8] or "").strip() or "day",
        }
        data["student_type"] = data["student_type"] if data["student_type"] in ("day", "boarding") else "day"

        errors = _validate_student_row(data, row_num)
        if errors:
            return ROW_FAIL, errors

        if session.query(Student).filter(Student.student_no == data["student_no"]).first():
            return ROW_FAIL, [f"第{row_num}行：学号 {data['student_no']} 已存在"]

        class_id = classrooms.get(data["class_name"])
        if not class_id:
            return ROW_FAIL, [f"第{row_num}行：班级「{data['class_name']}」不存在"]

        if class_id in graduated_class_ids:
            return ROW_FAIL, [f"第{row_num}行：班级「{data['class_name']}」已毕业，无法导入学生"]

        if teacher_class_ids is not None and class_id not in teacher_class_ids:
            return ROW_FAIL, [f"第{row_num}行：教师只能导入到自己负责的班级「{data['class_name']}」"]

        session.add(Student(
            student_no=data["student_no"],
            name=data["name"],
            gender=data["gender"],
            class_id=class_id,
            school_id=class_school.get(class_id),
            major=data["major"],
            birth_date=parse_date(data["birth_date"]),
            parent_name=data["parent_name"],
            parent_phone=data["parent_phone"],
            student_type=data["student_type"],
        ))
        session.flush()

        exists_user = get_student_account(session, class_id, data["name"])
        if not exists_user:
            session.add(User(
                username=data["name"],
                password_hash=hash_password("123456"),
                name=data["name"],
                role="student",
                school_id=class_school.get(class_id),
                class_id=class_id,
            ))
        return ROW_OK, []

    return run_import(
        db,
        user,
        file,
        import_type="student",
        audit_action="import_students",
        handle_row=handle_row,
    )


def list_import_history(db: Session, user, import_type: str = "", page: int = 1, page_size: int = 20) -> dict:
    """查询导入历史记录（分页）。"""
    page, page_size = normalize_page(page, page_size)
    stmt = select(ImportHistory)
    if import_type:
        stmt = stmt.where(ImportHistory.import_type == import_type)
    rows, total = paginate(db, stmt.order_by(ImportHistory.id.desc()), page, page_size)
    items = []
    for r in rows:
        d = to_dict(r)
        if r.errors:
            try:
                d["error_list"] = json.loads(r.errors)
            except (json.JSONDecodeError, TypeError):
                d["error_list"] = []
        else:
            d["error_list"] = []
        items.append(d)
    return {"items": items, "total": total}
