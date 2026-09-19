"""通用 Excel 批量导入骨架。

背景
----
学生导入（``imports_service.import_students``）与成绩导入（``scores_service.import_scores``）
原本各自实现了一套几乎相同的流程：

    扩展名校验 → 读取工作簿 → 逐行解析 → 业务校验 → 写入 → 审计 → 记录 ImportHistory

两份实现不仅重复，且**事务语义不一致**——学生导入在循环内 ``db.rollback()``，
某一行失败会连带回滚掉此前已 flush 的成功行，而计数仍按「部分成功」上报，
造成「界面显示成功 N 条、库里其实一条都没有」的静默数据丢失；成绩导入则相反，
失败行不回滚、只记录错误。

本模块抽取公共骨架并**统一事务语义**：

- **行级隔离**：每行写入包在 ``db.begin_nested()``（SAVEPOINT）里，单行失败只回滚该行，
  已成功行完整保留；
- **失败可观测**：系统异常走 ``logger.exception`` 落盘，不再只把 ``str(e)`` 回给前端。

使用方式
--------
调用方只提供 ``handle_row``（解析 + 业务校验 + 写入），其余（文件解析、空行跳过、
计数、事务、审计、导入历史、返回结构）由骨架统一处理。
"""
from __future__ import annotations

import json
import logging
import os
from io import BytesIO
from typing import Callable, Protocol

from fastapi import HTTPException
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models import ImportHistory
from app.services.workbench._common import audit

logger = logging.getLogger(__name__)

# handle_row 的返回状态
ROW_OK = 1  # 该行成功写入，计入 success
ROW_FAIL = 0  # 该行失败，errors 并入返回给前端的错误列表
ROW_SKIP = -1  # 该行跳过：不计入 total、不计入 success、不产生错误（如整行空值）

_ALLOWED_EXTS = {".xlsx", ".xls"}


class RowHandler(Protocol):
    """单行处理器：解析 → 业务校验 → 写入数据库（不 commit，由骨架统一提交）。"""

    def __call__(self, db: Session, row: tuple, row_num: int) -> tuple[int, list[str]]:
        """返回 ``(status, errors)``，status 取 ROW_OK / ROW_FAIL / ROW_SKIP。

        业务校验不通过时返回 ``(ROW_FAIL, [错误文案...])``；
        需要数据库写入时直接在函数内 ``db.add(...)``（可自行 ``db.flush()``），
        抛出任何异常都会被骨架捕获并回滚该行的 SAVEPOINT。
        """
        ...


def run_import(
    db: Session,
    user,
    file,
    *,
    import_type: str,
    audit_action: str,
    handle_row: Callable[[Session, tuple, int], tuple[int, list[str]]],
) -> dict:
    """执行 Excel 批量导入的公共流程。

    Args:
        db: 数据库会话。
        user: 当前操作用户（用于审计与导入历史）。
        file: FastAPI 的 ``UploadFile``。
        import_type: 导入历史记录的类别标识（如 ``"student"`` / ``"score"``）。
        audit_action: 审计动作名（如 ``"import_students"``）。
        handle_row: 单行处理器，见 :class:`RowHandler`。

    Returns:
        ``{"success": 成功条数, "total": 有效数据行数, "errors": 错误列表(前 50 条)}``
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail="仅支持 .xlsx / .xls 格式")

    contents = file.file.read()
    wb = load_workbook(BytesIO(contents))
    ws = wb.active

    rows = list(ws.iter_rows(min_row=2, values_only=True))
    if not rows:
        raise HTTPException(status_code=400, detail="文件中没有数据行")

    all_errors: list[str] = []
    success = 0
    total = 0

    for row_num, row in enumerate(rows, start=2):
        if not any(row):
            continue
        total += 1

        try:
            # SAVEPOINT：本行写入失败只回滚本行，此前已成功的行完整保留
            # （旧实现在此处 db.rollback() 会回滚整个事务，导致前序成功行静默丢失）
            with db.begin_nested():
                status, errors = handle_row(db, row, row_num)
            if status == ROW_OK:
                success += 1
            if errors:
                all_errors.extend(errors)
        except Exception as e:  # noqa: BLE001 - 单行失败不应中断整批导入
            # 系统异常必须落盘，否则只能看到前端一句 str(e) 而查不到堆栈
            logger.exception("[import:%s] 第 %s 行处理失败", import_type, row_num)
            all_errors.append(f"第{row_num}行：导入失败 - {str(e)}")

    db.commit()
    audit(db, user, audit_action, target=f"{file.filename or ''} 成功{success}条")

    db.add(
        ImportHistory(
            import_type=import_type,
            filename=file.filename or "",
            total_rows=total,
            success_rows=success,
            error_rows=len(all_errors),
            errors=json.dumps(all_errors[:100], ensure_ascii=False),
            user_id=user.id,
        )
    )
    db.commit()

    return {"success": success, "total": total, "errors": all_errors[:50]}
