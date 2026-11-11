/**
 * 前端共用的业务常量（口径须与后端 `backend/app/constants.py` 一致）。
 *
 * 这里只放「前端也要按同一口径判断、写错会静默改数」的量。成绩上下界就是典型：
 * 录入控件原先把上限写死成 100，而后端 `SCORE_MAX = 150`（语数外 150 分制常见），
 * `el-input-number` 会把 132 分**静默钳成 100** 再存库，学生的成绩、班级均分、
 * 分数段分布、周报均分全线偏低且没有任何报错（RBT-100）。
 *
 * ⚠️ 改这里必须同步改后端：`backend/app/constants.py::SCORE_MIN/SCORE_MAX`。
 */

/** 成绩下界（含），对应后端 `constants.SCORE_MIN` */
export const SCORE_MIN = 0

/** 成绩上界（含），对应后端 `constants.SCORE_MAX` */
export const SCORE_MAX = 150
