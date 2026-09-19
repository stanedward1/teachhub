import { createRouter, createWebHistory } from 'vue-router'
import { isStudent, isTeacher, getToken, getUser } from '../utils/auth'

const routes = [
  // ============ 学生端 ============
  {
    path: '/login',
    name: 'student-login',
    component: () => import('../views/student/Login.vue'),
  },
  {
    path: '/',
    component: () => import('../layout/StudentLayout.vue'),
    meta: { requiresStudent: true },
    children: [
      { path: '', redirect: '/homework' },
      {
        path: 'homework',
        name: 'homework',
        component: () => import('../views/student/HomeworkList.vue'),
      },
      {
        path: 'homework/:id',
        name: 'homework-detail',
        component: () => import('../views/student/HomeworkDetail.vue'),
      },
      {
        path: 'excellent',
        name: 'excellent',
        component: () => import('../views/student/ExcellentList.vue'),
      },
      {
        path: 'excellent/:id',
        name: 'excellent-detail',
        component: () => import('../views/student/ExcellentDetail.vue'),
      },
      {
        path: 'my-submissions',
        name: 'my-submissions',
        component: () => import('../views/student/MySubmissions.vue'),
      },
      {
        path: 'my-submissions/:id',
        name: 'my-submission-detail',
        component: () => import('../views/student/SubmissionDetail.vue'),
      },
      {
        path: 'practice',
        name: 'practice',
        component: () => import('../views/student/Practice.vue'),
      },
      { path: 'profile', name: 'profile', component: () => import('../views/student/Profile.vue') },
    ],
  },

  // ============ 管理端 ============
  {
    path: '/admin/login',
    name: 'admin-login',
    component: () => import('../views/admin/Login.vue'),
  },
  {
    path: '/admin/change-password',
    name: 'admin-change-password',
    component: () => import('../views/admin/ChangePassword.vue'),
    meta: { requiresTeacher: true },
  },
  {
    path: '/admin',
    component: () => import('../layout/AdminLayout.vue'),
    meta: { requiresTeacher: true },
    children: [
      { path: '', redirect: '/admin/dashboard' },
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('../views/admin/Dashboard.vue'),
      },
      {
        path: 'homework',
        name: 'admin-homework',
        component: () => import('../views/admin/Assignments.vue'),
      },
      {
        path: 'homework/:id/submissions',
        name: 'admin-submissions',
        component: () => import('../views/admin/AssignmentSubmissions.vue'),
      },
      {
        path: 'homework/:id/submissions/:submissionId',
        name: 'admin-submission-detail',
        component: () => import('../views/admin/SubmissionDetail.vue'),
      },
      {
        path: 'students',
        name: 'admin-students',
        component: () => import('../views/admin/Students.vue'),
      },
      {
        path: 'students/:id/profile',
        name: 'admin-student-profile',
        component: () => import('../views/admin/StudentProfile.vue'),
      },
      {
        path: 'classrooms',
        name: 'admin-classrooms',
        component: () => import('../views/admin/Classrooms.vue'),
      },
      {
        path: 'scores',
        name: 'admin-scores',
        component: () => import('../views/admin/Scores.vue'),
      },
      {
        path: 'leaves',
        name: 'admin-leaves',
        component: () => import('../views/admin/Leaves.vue'),
      },
      {
        path: 'communications',
        name: 'admin-communications',
        component: () => import('../views/admin/Communications.vue'),
      },
      {
        path: 'resources',
        name: 'admin-resources',
        component: () => import('../views/admin/Resources.vue'),
      },
      { path: 'exams', name: 'admin-exams', component: () => import('../views/admin/Exams.vue') },
      { path: 'seats', name: 'admin-seats', component: () => import('../views/admin/Seats.vue') },
      {
        path: 'worklogs',
        name: 'admin-worklogs',
        component: () => import('../views/admin/WorkLogs.vue'),
      },
      { path: 'plans', name: 'admin-plans', component: () => import('../views/admin/Plans.vue') },
      {
        path: 'schedules',
        name: 'admin-schedules',
        component: () => import('../views/admin/Schedules.vue'),
      },
      {
        path: 'activities',
        name: 'admin-activities',
        component: () => import('../views/admin/Activities.vue'),
      },
      { path: 'talks', name: 'admin-talks', component: () => import('../views/admin/Talks.vue') },
      {
        path: 'return-records',
        name: 'admin-return-records',
        component: () => import('../views/admin/ReturnRecords.vue'),
      },
      {
        path: 'performances',
        name: 'admin-performances',
        component: () => import('../views/admin/Performances.vue'),
      },
      {
        path: 'student-comments',
        name: 'admin-student-comments',
        component: () => import('../views/admin/StudentComments.vue'),
      },
      {
        path: 'reports',
        name: 'admin-reports',
        component: () => import('../views/admin/WeeklyReport.vue'),
      },
      { path: 'users', name: 'admin-users', component: () => import('../views/admin/Users.vue') },
      {
        path: 'schools',
        name: 'admin-schools',
        component: () => import('../views/admin/Schools.vue'),
      },
      {
        path: 'audit-logs',
        name: 'admin-audit-logs',
        component: () => import('../views/admin/AuditLogs.vue'),
      },
      {
        path: 'settings',
        name: 'admin-settings',
        component: () => import('../views/admin/Settings.vue'),
      },
      {
        path: 'platform-settings',
        name: 'admin-platform-settings',
        component: () => import('../views/admin/PlatformSettings.vue'),
      },
    ],
  },

  // ============ 移动端（班主任/管理员） ============
  {
    path: '/m/login',
    name: 'mobile-login',
    component: () => import('../mobile/views/Login.vue'),
  },
  {
    path: '/m/change-password',
    name: 'mobile-change-password',
    component: () => import('../mobile/views/ChangePassword.vue'),
    meta: { requiresTeacher: true },
  },
  {
    path: '/m',
    component: () => import('../mobile/layout/MobileLayout.vue'),
    meta: { requiresTeacher: true },
    children: [
      { path: '', redirect: '/m/home' },
      { path: 'home', name: 'm-home', component: () => import('../mobile/views/Home.vue') },
      {
        path: 'students',
        name: 'm-students',
        component: () => import('../mobile/views/StudentList.vue'),
      },
      {
        path: 'students/:id',
        name: 'm-student-overview',
        component: () => import('../mobile/views/StudentOverview.vue'),
      },
      {
        path: 'checkin',
        name: 'm-checkin',
        component: () => import('../mobile/views/Checkin.vue'),
      },
      {
        path: 'attendance-stats',
        name: 'm-attendance-stats',
        component: () => import('../mobile/views/AttendanceStats.vue'),
      },
      { path: 'record', name: 'm-record', component: () => import('../mobile/views/Record.vue') },
      {
        path: 'leaves',
        name: 'm-leaves',
        component: () => import('../mobile/views/LeaveList.vue'),
      },
    ],
  },

  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const hasToken = !!getToken()
  const user = getUser()
  const isTeacherArea = to.path.startsWith('/admin') || to.path.startsWith('/m')
  const isMobileArea = to.path.startsWith('/m')

  // 学生端页面：仅学生可访问（教师/管理员跳后台，不再预览）
  if (to.meta.requiresStudent) {
    if (!hasToken) return { path: '/login', query: { redirect: to.fullPath } }
    if (isTeacher()) return { path: '/admin' }
    // 学生强制改密
    if (user?.must_change_password && to.path !== '/profile') {
      return { path: '/profile' }
    }
    return true
  }

  // 管理端 + 移动端访问控制（教师/管理员）
  if (isTeacherArea && to.path !== '/admin/login' && to.path !== '/m/login') {
    if (!hasToken || !isTeacher()) {
      const loginPath = isMobileArea ? '/m/login' : '/admin/login'
      return { path: loginPath, query: { redirect: to.fullPath } }
    }
    // 强制改密：未改密的用户只能访问改密页
    const pwdPath = isMobileArea ? '/m/change-password' : '/admin/change-password'
    if (user?.must_change_password && to.path !== pwdPath) {
      return { path: pwdPath, query: { first: 1 } }
    }
  }

  // 已登录访问登录页 → 跳转对应首页/改密页
  if (to.path === '/admin/login' && hasToken && isTeacher()) {
    return { path: user?.must_change_password ? '/admin/change-password' : '/admin' }
  }
  if (to.path === '/m/login' && hasToken && isTeacher()) {
    return { path: user?.must_change_password ? '/m/change-password' : '/m/home' }
  }
  if (to.path === '/login' && hasToken && isStudent()) {
    return { path: user?.must_change_password ? '/profile' : '/' }
  }
  if (to.path === '/login' && hasToken && isTeacher()) {
    return { path: '/admin' }
  }

  // 已登录学生访问后台/移动端时，跳转到学生端
  if (hasToken && isStudent() && isTeacherArea) {
    return { path: '/' }
  }

  return true
})

export default router
