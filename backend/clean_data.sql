-- ============================================================
-- TeachHub 数据清理脚本
-- 用途：清空所有业务数据，仅保留教师/管理员账号 + 学校/班级/设置结构
-- 用法：mysql -uroot -p < clean_data.sql
--       或在 MySQL 客户端中 source 本文件
-- 说明：临时关闭外键检查后批量删除，最后恢复，无需关心删除顺序
-- ============================================================

USE teachhub;

SET FOREIGN_KEY_CHECKS = 0;

-- 1) 作业 / 提交 / 优秀作品链
DELETE FROM work_comments;
DELETE FROM excellent_works;
DELETE FROM submission_comments;
DELETE FROM submissions;
DELETE FROM assignments;

-- 2) 学生业务数据
DELETE FROM performances;
DELETE FROM talks;
DELETE FROM scores;
DELETE FROM leaves;
DELETE FROM communications;
DELETE FROM student_comments;
DELETE FROM return_records;
DELETE FROM student_profile_tags;
DELETE FROM student_board_history;
DELETE FROM attendance;

-- 3) 教师 / 班级工作数据
DELETE FROM weekly_reports;
DELETE FROM activities;
DELETE FROM schedules;
DELETE FROM seats;
DELETE FROM class_plans;
DELETE FROM teacher_plans;
DELETE FROM work_logs;
DELETE FROM import_history;
DELETE FROM resources;
DELETE FROM exams;
DELETE FROM operation_logs;

-- 4) 学生档案 + 学生账号
DELETE FROM students;
DELETE FROM users WHERE role = 'student';

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 保留的数据：
--   users（teacher / admin 账号）
--   schools（学校）、classrooms（班级）、class_teachers（教师-班级关联）、settings（系统设置）
--
-- 可选：如需重置自增 ID，执行以下（对需要重置的表逐条执行）：
--   ALTER TABLE students AUTO_INCREMENT = 1;
-- ============================================================
