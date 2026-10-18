import request from './request'

// ============ 通用 CRUD 工厂 ============
// 各资源接口的四件套只有 URL 段不同，统一由此生成，避免 13 份逐字复制。
// `methods` 显式声明该资源真实存在的方法：后端没有 update 的资源不要凭空暴露。
const CRUD_METHODS = {
  list: (base) => (params) => request.get(`/api/${base}`, { params }),
  create: (base) => (data) => request.post(`/api/${base}`, data),
  update: (base) => (id, data) => request.put(`/api/${base}/${id}`, data),
  remove: (base) => (id) => request.delete(`/api/${base}/${id}`),
}

function crud(base, methods = Object.keys(CRUD_METHODS)) {
  return Object.fromEntries(methods.map((m) => [m, CRUD_METHODS[m](base)]))
}

// ============ 认证 ============
export const authApi = {
  login: (data) => request.post('/api/auth/login', data),
  // 注意：刷新令牌（/api/auth/refresh）刻意**不在**本封装内。access token 过期的静默刷新
  // 由 api/request.js 的 401 拦截器用「裸 axios 实例」直接发起（避免刷新请求自身 401 时递归），
  // 前端无其他刷新入口（原 authApi.refresh 零调用，已删除）。
  // 退出登录：注销服务端 refresh token
  logout: (refreshToken) => request.post('/api/auth/logout', { refresh_token: refreshToken }),
  register: (data) => request.post('/api/auth/register', data),
  changePassword: (data) => request.put('/api/auth/password', data),
  uploadAvatar: (formData) =>
    request.post('/api/auth/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  // 登录页学校下拉（无需登录）
  publicSchools: () => request.get('/api/auth/schools'),
  // 学生登录页注册开关（无需登录）
  registrationStatus: () => request.get('/api/auth/registration-status'),
}

// ============ 公共 ============
export const metaApi = {
  classes: (schoolId) =>
    request.get('/api/meta/classes', { params: schoolId ? { school_id: schoolId } : {} }),
  practice: () => request.get('/api/meta/practice'),
}

// ============ 租户（学校）管理：平台超管 ============
export const schoolApi = {
  ...crud('schools'),
  setStatus: (id, status) => request.put(`/api/schools/${id}/status`, { status }),
}

// ============ 作业提交平台 ============
export const homeworkApi = {
  assignments: (params) => request.get('/api/homework/assignments', { params }),
  assignment: (id) => request.get(`/api/homework/assignments/${id}`),
  createAssignment: (data) => request.post('/api/homework/assignments', data),
  updateAssignment: (id, data) => request.put(`/api/homework/assignments/${id}`, data),
  deleteAssignment: (id) => request.delete(`/api/homework/assignments/${id}`),
  submissions: (id, params) =>
    request.get(`/api/homework/assignments/${id}/submissions`, { params }),
  // 未交名单：该作业下发班级中尚未提交的学生
  unsubmitted: (id) => request.get(`/api/homework/assignments/${id}/unsubmitted`),
  // 分数段分布：各分数段人数 + 已评分学生（含有效分）+ 未交学生单列
  scoreDistribution: (id) =>
    request.get(`/api/homework/assignments/${id}/score-distribution`),
  submissionDetail: (id) => request.get(`/api/homework/submissions/${id}`),
  // AI 批改（教师手动触发）：整份作业批量批改 / 单份提交批改
  aiGradeAssignment: (id) => request.post(`/api/homework/assignments/${id}/ai-grade`),
  // AI 批改进度（轮询用）：返回 {total,success,failed,pending,ungraded,done,finished}
  aiGradeProgress: (id) => request.get(`/api/homework/assignments/${id}/ai-grade/progress`),
  aiGradeSubmission: (id) => request.post(`/api/homework/submissions/${id}/ai-grade`),
  addSubmissionComment: (id, data) =>
    request.post(`/api/homework/submissions/${id}/comments`, data),
  deleteSubmissionComment: (submissionId, commentId) =>
    request.delete(`/api/homework/submissions/${submissionId}/comments/${commentId}`),
  submit: (id, data) => request.post(`/api/homework/assignments/${id}/submissions`, data),
  mySubmissions: () => request.get('/api/homework/my-submissions'),
  markExcellent: (submissionId, data) =>
    request.post(`/api/homework/submissions/${submissionId}/excellent`, data),
  unmarkExcellent: (submissionId) =>
    request.delete(`/api/homework/submissions/${submissionId}/excellent`),
  excellent: () => request.get('/api/homework/excellent'),
  excellentDetail: (id) => request.get(`/api/homework/excellent/${id}`),
  addComment: (id, data) => request.post(`/api/homework/excellent/${id}/comments`, data),
  // ============ AI 学伴（设计 §4.2）============
  // 学生侧（可写）：提问 / 取历史 / 清空本会话。依赖 require_student，教师不可调用。
  // 注意：ask 无幂等性，重试会再扣 1 次额度（设计 §2.2.2 方案 A）。
  companionAsk: (id, data) => request.post(`/api/homework/assignments/${id}/companion/ask`, data),
  companionHistory: (id) => request.get(`/api/homework/assignments/${id}/companion/history`),
  // 每生独立配额：查询本生今日剩余次数（只读；同学伴开关由后端统一判定）
  companionQuota: (id) => request.get(`/api/homework/assignments/${id}/companion/quota`),
  clearCompanion: (id) => request.delete(`/api/homework/assignments/${id}/companion`),
  // 教师侧（只读，设计 §14.2）：本班学生的学伴会话列表 / 单会话完整消息。
  // 🔴 会话列表是纯附加信息：调用方（AssignmentSubmissions）已按失败降级为空处理，
  // 故允许传 `_silent: true` 抑制全局拦截器的错误弹窗（避免噪音）。
  companionConversations: (id, params, config = {}) =>
    request.get(`/api/homework/assignments/${id}/companion/conversations`, { params, ...config }),
  companionConversationDetail: (conversationId) =>
    request.get(`/api/homework/companion/conversations/${conversationId}`),
}

// ============ 基础数据 ============
export const studentApi = {
  classrooms: (params) => request.get('/api/classrooms', { params }),
  createClassroom: (data) => request.post('/api/classrooms', data),
  updateClassroom: (id, data) => request.put(`/api/classrooms/${id}`, data),
  deleteClassroom: (id) => request.delete(`/api/classrooms/${id}`),
  classTeachers: (classId) => request.get(`/api/classrooms/${classId}/teachers`),
  addClassTeacher: (classId, data) => request.post(`/api/classrooms/${classId}/teachers`, data),
  removeClassTeacher: (classId, teacherId) =>
    request.delete(`/api/classrooms/${classId}/teachers/${teacherId}`),
  list: (params) => request.get('/api/students', { params }),
  create: (data) => request.post('/api/students', data),
  update: (id, data) => request.put(`/api/students/${id}`, data),
  remove: (id) => request.delete(`/api/students/${id}`),
  export: (params) => request.get('/api/students/export', { params, responseType: 'blob' }),
  resetPassword: (id, data) => request.put(`/api/students/${id}/password`, data),
  batchResetPassword: (data) => request.put('/api/students/password/batch', data),
  boardTypeStats: (params) => request.get('/api/students/board-type-stats', { params }),
  template: () => request.get('/api/students/template', { responseType: 'blob' }),
  import: (formData) =>
    request.post('/api/students/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  profile: (id) => request.get(`/api/students/${id}/profile`),
  addTag: (id, data) => request.post(`/api/students/${id}/tags`, data),
  removeTag: (studentId, tagId) => request.delete(`/api/students/${studentId}/tags/${tagId}`),
  uploadAvatar: (id, formData) =>
    request.post(`/api/students/${id}/avatar`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  boardHistory: (id) => request.get(`/api/students/${id}/board-history`),
}

// ============ 教师工作台 ============
export const scoreApi = {
  ...crud('scores'),
  analysis: (params) => request.get('/api/scores/analysis', { params }),
  export: (params) => request.get('/api/scores/export', { params, responseType: 'blob' }),
  template: () => request.get('/api/scores/template', { responseType: 'blob' }),
  import: (formData) =>
    request.post('/api/scores/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}

export const leaveApi = crud('leaves')

export const attendanceApi = {
  list: (params) => request.get('/api/attendance', { params }),
  checkin: (data) => request.post('/api/attendance/checkin', data),
  summary: (params) => request.get('/api/attendance/summary', { params }),
}

export const communicationApi = crud('communications', ['list', 'create', 'remove'])

export const resourceApi = crud('resources', ['list', 'create', 'remove'])

export const examApi = {
  list: (params) => request.get('/api/exams', { params }),
  upload: (formData, params = {}) =>
    request.post('/api/exams/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params,
    }),
  update: (id, data) => request.put(`/api/exams/${id}`, data),
  download: (id) => request.get(`/api/exams/${id}/download`, { responseType: 'blob' }),
  remove: (id) => request.delete(`/api/exams/${id}`),
}

export const seatApi = {
  get: (classId) => request.get('/api/seats', { params: { class_id: classId } }),
  save: (data) => request.put('/api/seats', data),
}

// ============ 班级日志 ============
export const workLogApi = crud('work-logs')

const classPlan = crud('class-plans')
const teacherPlan = crud('teacher-plans')

export const planApi = {
  classPlans: classPlan.list,
  createClassPlan: classPlan.create,
  updateClassPlan: classPlan.update,
  removeClassPlan: classPlan.remove,
  teacherPlans: teacherPlan.list,
  createTeacherPlan: teacherPlan.create,
  updateTeacherPlan: teacherPlan.update,
  removeTeacherPlan: teacherPlan.remove,
}

export const scheduleApi = crud('schedules')

export const activityApi = crud('activities', ['list', 'create', 'remove'])

export const talkApi = crud('talks', ['list', 'create', 'remove'])

export const returnRecordApi = crud('return-records', ['list', 'create', 'remove'])

export const performanceApi = {
  ...crud('performances', ['list', 'create', 'remove']),
  // 筛选范围内的积分汇总（净变动 / 累计加分 / 累计扣分 / 记录数 / 涉及学生数）
  summary: (params) => request.get('/api/performances/summary', { params }),
}

export const studentCommentApi = {
  ...crud('student-comments'),
  suggest: (studentId) =>
    request.get('/api/student-comments/suggest', { params: { student_id: studentId } }),
}

// ============ 系统管理 ============
export const adminApi = {
  users: (params) => request.get('/api/admin/users', { params }),
  createUser: (data) => request.post('/api/admin/users', data),
  updateUser: (id, data) => request.put(`/api/admin/users/${id}`, data),
  resetPassword: (id, data) => request.put(`/api/admin/users/${id}/password`, data),
  removeUser: (id) => request.delete(`/api/admin/users/${id}`),
  settings: () => request.get('/api/settings'),
  setSetting: (key, value) => request.put(`/api/settings/${key}`, { value }),
  upgradeGrade: () => request.post('/api/settings/upgrade-grade'),
  dashboard: () => request.get('/api/stats/dashboard'),
  auditLogs: (params) => request.get('/api/admin/audit-logs', { params }),
  auditLogActions: () => request.get('/api/admin/audit-logs/actions'),
  auditLogStats: (params) => request.get('/api/admin/audit-logs/stats', { params }),
  platformOverview: () => request.get('/api/admin/platform/overview'),
  platformRegistration: () => request.get('/api/admin/platform/registration'),
  setPlatformRegistration: (data) => request.put('/api/admin/platform/registration', data),
  // 学生单设备在线（平台级，缺省开启）：开启后学生登录会把先登录的设备挤下线
  platformStudentDevice: () => request.get('/api/admin/platform/student-device'),
  setPlatformStudentDevice: (data) => request.put('/api/admin/platform/student-device', data),
  // AI 批改（平台超管专属）：凭证只写不回显，读接口仅返回掩码
  aiCredential: () => request.get('/api/admin/platform/ai-credential'),
  setAiCredential: (data) => request.put('/api/admin/platform/ai-credential', data),
  testAiCredential: (data) => request.post('/api/admin/platform/ai-credential/test', data),
  aiGrading: () => request.get('/api/admin/platform/ai-grading'),
  setAiGrading: (data) => request.put('/api/admin/platform/ai-grading', data),
  // 校级 AI 能力配置（超管专用，docs/DESIGN-AI校级能力.md §3 D5）
  schoolAiSettings: (schoolId) => request.get(`/api/admin/schools/${schoolId}/ai-settings`),
  setSchoolAiSettings: (schoolId, data) =>
    request.put(`/api/admin/schools/${schoolId}/ai-settings`, data),
}

// ============ 文件上传 ============
export function uploadFile(file) {
  const form = new FormData()
  form.append('file', file)
  return request.post('/api/uploads', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ============ 导入历史 ============
export const importApi = {
  // 第二参 config 用于传输层开关（如 `_silent: true`），
  // 不要混进 params —— 那会被 axios 序列化成查询参数发给服务端。
  history: (params, config = {}) => request.get('/api/import-history', { params, ...config }),
}

// ============ 班级周报 ============
export const reportApi = {
  weeklyData: (params) => request.get('/api/reports/weekly-data', { params }),
  list: (params) => request.get('/api/reports', { params }),
  save: (data) => request.post('/api/reports', data),
  remove: (id) => request.delete(`/api/reports/${id}`),
}
