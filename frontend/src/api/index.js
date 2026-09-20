import request from './request'

// ============ 认证 ============
export const authApi = {
  login: (data) => request.post('/api/auth/login', data),
  // 刷新令牌（access token 过期时使用）；失败返回 401
  refresh: (refreshToken) => request.post('/api/auth/refresh', { refresh_token: refreshToken }),
  // 退出登录：注销服务端 refresh token
  logout: (refreshToken) => request.post('/api/auth/logout', { refresh_token: refreshToken }),
  register: (data) => request.post('/api/auth/register', data),
  me: () => request.get('/api/auth/me'),
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
  list: () => request.get('/api/schools'),
  create: (data) => request.post('/api/schools', data),
  update: (id, data) => request.put(`/api/schools/${id}`, data),
  remove: (id) => request.delete(`/api/schools/${id}`),
  setStatus: (id, status) => request.put(`/api/schools/${id}/status`, { status }),
}

// ============ 作业提交平台 ============
export const homeworkApi = {
  assignments: (params) => request.get('/api/homework/assignments', { params }),
  assignment: (id) => request.get(`/api/homework/assignments/${id}`),
  createAssignment: (data) => request.post('/api/homework/assignments', data),
  updateAssignment: (id, data) => request.put(`/api/homework/assignments/${id}`, data),
  deleteAssignment: (id) => request.delete(`/api/homework/assignments/${id}`),
  submissions: (id) => request.get(`/api/homework/assignments/${id}/submissions`),
  // 未交名单：该作业下发班级中尚未提交的学生
  unsubmitted: (id) => request.get(`/api/homework/assignments/${id}/unsubmitted`),
  submissionDetail: (id) => request.get(`/api/homework/submissions/${id}`),
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
}

// ============ 基础数据 ============
export const studentApi = {
  schools: () => request.get('/api/schools'),
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
  list: (params) => request.get('/api/scores', { params }),
  create: (data) => request.post('/api/scores', data),
  update: (id, data) => request.put(`/api/scores/${id}`, data),
  remove: (id) => request.delete(`/api/scores/${id}`),
  analysis: (params) => request.get('/api/scores/analysis', { params }),
  export: (params) => request.get('/api/scores/export', { params, responseType: 'blob' }),
  template: () => request.get('/api/scores/template', { responseType: 'blob' }),
  import: (formData) =>
    request.post('/api/scores/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}

export const leaveApi = {
  list: (params) => request.get('/api/leaves', { params }),
  create: (data) => request.post('/api/leaves', data),
  update: (id, data) => request.put(`/api/leaves/${id}`, data),
  remove: (id) => request.delete(`/api/leaves/${id}`),
}

export const attendanceApi = {
  list: (params) => request.get('/api/attendance', { params }),
  checkin: (data) => request.post('/api/attendance/checkin', data),
  summary: (params) => request.get('/api/attendance/summary', { params }),
}

export const communicationApi = {
  list: (params) => request.get('/api/communications', { params }),
  create: (data) => request.post('/api/communications', data),
  remove: (id) => request.delete(`/api/communications/${id}`),
}

export const resourceApi = {
  list: (params) => request.get('/api/resources', { params }),
  create: (data) => request.post('/api/resources', data),
  remove: (id) => request.delete(`/api/resources/${id}`),
}

export const examApi = {
  list: (params) => request.get('/api/exams', { params }),
  upload: (formData) =>
    request.post('/api/exams/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
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
export const workLogApi = {
  list: (params) => request.get('/api/work-logs', { params }),
  create: (data) => request.post('/api/work-logs', data),
  update: (id, data) => request.put(`/api/work-logs/${id}`, data),
  remove: (id) => request.delete(`/api/work-logs/${id}`),
}

export const planApi = {
  classPlans: (params) => request.get('/api/class-plans', { params }),
  createClassPlan: (data) => request.post('/api/class-plans', data),
  updateClassPlan: (id, data) => request.put(`/api/class-plans/${id}`, data),
  removeClassPlan: (id) => request.delete(`/api/class-plans/${id}`),
  teacherPlans: (params) => request.get('/api/teacher-plans', { params }),
  createTeacherPlan: (data) => request.post('/api/teacher-plans', data),
  updateTeacherPlan: (id, data) => request.put(`/api/teacher-plans/${id}`, data),
  removeTeacherPlan: (id) => request.delete(`/api/teacher-plans/${id}`),
}

export const scheduleApi = {
  list: (params) => request.get('/api/schedules', { params }),
  create: (data) => request.post('/api/schedules', data),
  remove: (id) => request.delete(`/api/schedules/${id}`),
}

export const activityApi = {
  list: (params) => request.get('/api/activities', { params }),
  create: (data) => request.post('/api/activities', data),
  remove: (id) => request.delete(`/api/activities/${id}`),
}

export const talkApi = {
  list: (params) => request.get('/api/talks', { params }),
  create: (data) => request.post('/api/talks', data),
  remove: (id) => request.delete(`/api/talks/${id}`),
}

export const returnRecordApi = {
  list: (params) => request.get('/api/return-records', { params }),
  create: (data) => request.post('/api/return-records', data),
  remove: (id) => request.delete(`/api/return-records/${id}`),
}

export const performanceApi = {
  list: (params) => request.get('/api/performances', { params }),
  // 筛选范围内的积分汇总（净变动 / 累计加分 / 累计扣分 / 记录数 / 涉及学生数）
  summary: (params) => request.get('/api/performances/summary', { params }),
  create: (data) => request.post('/api/performances', data),
  remove: (id) => request.delete(`/api/performances/${id}`),
}

export const studentCommentApi = {
  list: (params) => request.get('/api/student-comments', { params }),
  create: (data) => request.post('/api/student-comments', data),
  update: (id, data) => request.put(`/api/student-comments/${id}`, data),
  remove: (id) => request.delete(`/api/student-comments/${id}`),
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
  history: (params) => request.get('/api/import-history', { params }),
}

// ============ 班级周报 ============
export const reportApi = {
  weeklyData: (params) => request.get('/api/reports/weekly-data', { params }),
  list: (params) => request.get('/api/reports', { params }),
  save: (data) => request.post('/api/reports', data),
  remove: (id) => request.delete(`/api/reports/${id}`),
}
