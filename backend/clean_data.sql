-- ============================================================
-- TeachHub 数据清理脚本
-- 用途：清空所有业务数据，仅保留「学校 / 班级 / 教师账号 / 系统设置」结构
-- 用法：mysql -uroot -p teachhub < clean_data.sql
--       或在 MySQL 客户端中 source 本文件
-- 说明：
--   1. 临时关闭外键检查，批量删除，最后恢复
--   2. 整体包裹在事务中，出错自动回滚，保证原子性
--   3. 覆盖所有业务表（含 assignment_attachments），无孤儿数据残留
-- ============================================================

USE teachhub;

SET FOREIGN_KEY_CHECKS = 0;
START TRANSACTION;

-- ------------------------------------------------------------
-- 1) 作业 / 提交 / 优秀作品链（含附件）
-- ------------------------------------------------------------
DELETE FROM work_comments;          -- 优秀作品评论（叶子）
DELETE FROM excellent_works;        -- 优秀作品
DELETE FROM submission_comments;    -- 作业点评
DELETE FROM submissions;            -- 作业提交
DELETE FROM assignment_attachments; -- 作业附件（新增：外键指向 assignments）
DELETE FROM assignments;            -- 作业任务

-- ------------------------------------------------------------
-- 2) 学生业务数据（student_id 引用 students.id）
-- ------------------------------------------------------------
DELETE FROM performances;           -- 表现记录
DELETE FROM talks;                  -- 谈心
DELETE FROM scores;                 -- 成绩
DELETE FROM leaves;                 -- 请假
DELETE FROM communications;         -- 家校沟通
DELETE FROM student_comments;       -- 学生评语
DELETE FROM return_records;         -- 返校记录
DELETE FROM student_profile_tags;   -- 画像标签
DELETE FROM student_board_history;  -- 学生看板历史
DELETE FROM attendance;             -- 考勤

-- ------------------------------------------------------------
-- 3) 教师 / 班级工作数据
-- ------------------------------------------------------------
DELETE FROM weekly_reports;         -- 周报
DELETE FROM activities;             -- 班级活动
DELETE FROM schedules;              -- 课程表
DELETE FROM seats;                  -- 座位表
DELETE FROM class_plans;            -- 班级计划
DELETE FROM teacher_plans;          -- 教师计划
DELETE FROM work_logs;              -- 工作日志
DELETE FROM import_history;         -- 导入历史
DELETE FROM resources;              -- 资源
DELETE FROM exams;                  -- 试卷
DELETE FROM operation_logs;         -- 操作日志

-- ------------------------------------------------------------
-- 4) 学生档案 + 学生账号
--    顺序：先删账号（users.class_id 外键指向 classrooms，不受影响），
--          再删档案（students），因外键检查已关闭，顺序无强制约束。
-- ------------------------------------------------------------
DELETE FROM users WHERE role = 'student';
DELETE FROM students;

COMMIT;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 保留的数据：
--   users（teacher / school_admin / super_admin 账号）
--   schools（学校）、classrooms（班级）、class_teachers（教师-班级关联）
--   settings（系统设置）
--
-- 可选：如需重置自增 ID，对需要重置的表逐条执行，例如：
--   ALTER TABLE students AUTO_INCREMENT = 1;
-- ============================================================
