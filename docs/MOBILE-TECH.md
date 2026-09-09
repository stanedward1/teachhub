# TeachHub 移动端技术方案（Product Brief）

> 状态：草稿 v0.1 ｜ 配套 `docs/REQUIREMENTS.md`（移动端 MVP PRD）｜ 面向工程评审

## 1. 技术选型结论

- **独立移动端**：独立路由前缀 `/m`，引入 **Vant 4**（移动端组件库）
- **复用后端**：FastAPI + 现有权限体系（`require_teacher`、退学/毕业校验），不新起服务
- **复用前端栈**：Vue3 + Vite，移动端与桌面端共存（桌面端 Element Plus 不受影响）
- **不引入**：小程序、原生 App、第二套构建

## 2. 后端接口清单（6 个 P0）

> 原则：能复用现有接口就复用；只为「学生速查」这类移动端性能敏感场景新增轻量聚合接口；「考勤打卡」为唯一全新功能。

| P0 | 接口 | 复用/新增 | 说明 |
| --- | ---- | ---- | ---- |
| R1 登录 | `POST /api/auth/login`、`GET /api/auth/me` | ✅ 复用 | 教师/管理员账号登录，Token 机制不变 |
| R2 学生速查 | `GET /api/students`（keyword/dropped_out/class_id） | ✅ 复用 | 搜索学生列表 |
| R2 学生速查 | `GET /api/students/{id}/profile` | ⚠️ 复用（偏重） | 画像+成绩+积分完整数据，移动端可先复用 |
| R2 学生速查 | `GET /api/mobile/students/{id}/overview` | 🆕 新增（建议） | 画像概览+成绩摘要+积分摘要，**一次请求**返回，避免移动端多次拉取 |
| R3 随手记表现 | `POST /api/performances` | ✅ 复用 | 已自动联动积分；学生选择复用 `GET /api/students?dropped_out=false` |
| R4 考勤打卡 | `POST /api/attendance/checkin`、`GET /api/attendance` | 🆕 全新 | 见第 3 节 |
| R5 请假查看/审批 | `GET /api/leaves`、`PUT /api/leaves/{id}` | ✅ 复用 | 「销假」= 改 `status`；完整审批流见第 6 节待决项 |
| R6 谈心速记 | `POST /api/talks` | ✅ 复用 | 即时保存，与桌面端打通 |

### 移动端新增接口约定（`/api/mobile/*`）

| 接口 | 方法 | 用途 | 返回（精简字段） |
| ---- | ---- | ---- | ---- |
| `/api/mobile/students` | GET | 学生搜索列表 | id、name、student_no、class_name、avatar、student_type、is_dropped_out |
| `/api/mobile/students/{id}/overview` | GET | 学生速查概览 | 基本信息 + 五维雷达概览 + 最近成绩 + 积分合计 |

> 移动端接口应**精简字段、免桌面端重量级序列化**，并复用后端已有的 `filter_students_by_teacher`（班主任隔离）与 `ensure_student_operable`（退学/毕业限制）。

## 3. 考勤打卡（唯一全新功能）

现有系统**没有每日点名/打卡**，`leaves` 表只存请假记录。P0 的「考勤打卡」需新增：

- **数据模型** `Attendance`（表 `attendance`）
  - `id`、`class_id`（FK classrooms）、`student_id`（FK students）、`date`（日期）、`status`（出勤/缺勤/请假/迟到）、`created_at`
  - 唯一约束：`(class_id, student_id, date)` 防重复打卡
- **接口**
  - `POST /api/attendance/checkin`：按班级批量提交点名结果（payload 含 `class_id`、`date`、`[{student_id, status}]`），返回成功/失败明细
  - `GET /api/attendance?class_id=&date=`：查询某班某日考勤
  - （可选）`GET /api/attendance/summary?class_id=&date=`：出勤率统计
- **配套**：新增 Alembic 迁移（参考现有 `c8d5e3f2b1a0` 的写法）
- **权限**：`require_teacher` + 班主任只能点自己班级（复用 `is_teacher_class_owner`）；退学/毕业学生不参与点名

## 4. 前端路由结构（独立 `/m`）

```
/m/login                    移动端登录（可复用 /admin/login 逻辑）
/m                          移动端布局 MobileLayout（底部 TabBar，requiresTeacher）
  ├── /m/home                首页（待办、今日请假速览）
  ├── /m/students            学生速查列表
  │     └── /m/students/:id  学生画像概览
  ├── /m/checkin             考勤打卡
  ├── /m/leaves              请假查看/销假
  └── /m/record              快捷记录（表现/谈心，TabBar 中央大按钮入口）
```

- 路由守卫复用现有 `router.beforeEach`，对 `/m` 前缀增加 `requiresTeacher` 校验
- 移动端与桌面端**共存**：`/admin` 走 Element Plus，`/m` 走 Vant，互不干扰

## 5. 前端组件拆分

```
src/
├── mobile/                       # 移动端独立目录
│   ├── layout/MobileLayout.vue   # 底部 TabBar + 顶部导航（Vant Tabbar）
│   ├── views/
│   │   ├── Home.vue              # 首页速览
│   │   ├── StudentList.vue       # 学生速查列表（Vant Search + List）
│   │   ├── StudentOverview.vue   # 画像概览（复用 ECharts 雷达，或轻量进度条）
│   │   ├── Checkin.vue           # 考勤打卡（Vant 单选组批量标记）
│   │   ├── LeaveList.vue         # 请假列表 + 销假
│   │   └── Record.vue            # 快捷记录（ActionSheet 选表现/谈心）
│   ├── components/
│   │   ├── StudentPicker.vue     # 学生选择器（Vant Picker，复用后端学生列表）
│   │   └── StatCard.vue          # 数据速览卡片
│   └── api/mobile.js             # 移动端专用接口（/api/mobile/*）
```

- **API 层**：复用 `api/index.js` 的 `studentApi/performanceApi/talkApi/leaveApi`，新增 `mobile.js` 放 `/api/mobile/*` 与考勤接口
- **Vant 引入**：按需引入（推荐 `unplugin-vue-components`）避免全量打包

## 6. 关键技术决策点（待工程评审）

| # | 决策点 | 选项 | 倾向 |
| --- | ---- | ---- | ---- |
| 1 | 学生速查是否上 `/api/mobile/*` 聚合接口 | A. 直接复用现有 profile 接口；B. 新增轻量聚合接口 | **B**（移动端性能/流量敏感） |
| 2 | 考勤打卡状态枚举 | 出勤/缺勤/请假/迟到 vs 简化版 | 建议含「迟到」，与请假联动 |
| 3 | 请假「审批」语义 | 现有系统请假是**教师登记制**，无「学生发起→教师审批」闭环 | P0 先做「查看+销假」；若需完整审批流，需新增学生端请假申请（另立项） |
| 4 | Vant 引入方式 | 全量 vs 按需 | 按需，控制包体积 |
| 5 | 移动端登录入口 | 独立 `/m/login` vs 复用 `/admin/login` | 独立（后续可接短信/扫码） |

## 7. 里程碑建议

- **M1**：移动端脚手架 + 登录 + 学生速查 + 快捷记录（复用为主，验证高频链路）
- **M2**：考勤打卡（全新，含数据模型/迁移/接口）+ 请假查看销假
- **M3**：首页速览 + PWA 可安装 + 待办提醒（对应 PRD 的 P1）
