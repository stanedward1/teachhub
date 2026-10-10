/**
 * 角色常量、中文标签与权限谓词的单源（single source of truth）。
 *
 * 收敛自 Users.vue（用户表格 roleText/roleType + 四份「教师不可管理教师/管理员」谓词）
 * 与 AdminLayout.vue（头部角色文案）中重复出现的硬编码映射，避免多处漂移。
 */

export const ROLES = {
  TEACHER: 'teacher',
  SCHOOL_ADMIN: 'school_admin',
  SUPER_ADMIN: 'super_admin',
  STUDENT: 'student',
}

export const ROLE_LABELS = {
  super_admin: '平台超管',
  school_admin: '学校管理员',
  teacher: '教师',
  student: '学生',
}

// el-tag 颜色类型（Users.vue 用户表格角色列）
export const ROLE_TAG_TYPES = {
  super_admin: 'danger',
  school_admin: 'warning',
  teacher: 'primary',
  student: 'info',
}

/** 角色中文标签；未知角色返回 undefined（与原 Users.vue roleText 行为一致） */
export function roleLabel(role) {
  return ROLE_LABELS[role]
}

/** 角色对应的 el-tag 颜色类型；未知角色返回 undefined */
export function roleTagType(role) {
  return ROLE_TAG_TYPES[role]
}

/** 是否为教职员工角色（教师/学校管理员/平台超管，即除学生外的全部角色） */
export function isStaffRole(role) {
  return role === ROLES.TEACHER || role === ROLES.SCHOOL_ADMIN || role === ROLES.SUPER_ADMIN
}

/** 当前登录者是否为普通教师（非任何管理员） */
export function isTeacherRole(role) {
  return role === ROLES.TEACHER
}

/**
 * myRole 是否可对 rowRole 的用户执行管理操作（重置密码/删除/改角色/改姓名）。
 * 语义与原 Users.vue 四份谓词一致：普通教师不可管理其他教职员工。
 *
 * @param {string|undefined} myRole 当前登录用户的角色（来自 utils/auth getUser()）
 * @param {string|undefined} rowRole 目标行用户的角色
 */
export function canManageUser(myRole, rowRole) {
  return !(isTeacherRole(myRole) && isStaffRole(rowRole))
}
