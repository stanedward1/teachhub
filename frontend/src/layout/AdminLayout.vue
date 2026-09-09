<template>
  <el-container class="admin-layout">
    <!-- 移动端遮罩 -->
    <div v-if="mobileMenuOpen" class="mobile-mask" @click="mobileMenuOpen = false"></div>

    <!-- 侧边栏 -->
    <el-aside :width="collapsed ? '64px' : '220px'" class="aside" :class="{ 'mobile-open': mobileMenuOpen }">
      <div class="brand" @click="$router.push('/admin/dashboard')">
        <span class="brand-mark">T</span>
        <transition name="fade">
          <span v-if="!collapsed" class="brand-text">TechHub</span>
        </transition>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        router
        class="menu"
        background-color="transparent"
        text-color="rgba(255,255,255,0.65)"
        active-text-color="#fff"
        @select="mobileMenuOpen = false"
      >
        <el-menu-item index="/admin/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>数据看板</span>
        </el-menu-item>

        <el-sub-menu index="hw">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>在线作业管理</span>
          </template>
          <el-menu-item index="/admin/homework">任务列表</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="workbench">
          <template #title>
            <el-icon><Briefcase /></el-icon>
            <span>教师工作台</span>
          </template>
          <el-menu-item index="/admin/students">学生管理</el-menu-item>
          <el-menu-item index="/admin/scores">成绩管理</el-menu-item>
          <el-menu-item index="/admin/leaves">考勤管理</el-menu-item>
          <el-menu-item index="/admin/communications">家校沟通</el-menu-item>
          <el-menu-item index="/admin/resources">资源管理</el-menu-item>
          <el-menu-item index="/admin/exams">试卷管理</el-menu-item>
          <el-menu-item index="/admin/seats">座位表</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="classlog">
          <template #title>
            <el-icon><Notebook /></el-icon>
            <span>班级日志</span>
          </template>
          <el-menu-item index="/admin/classrooms">班级管理</el-menu-item>
          <el-menu-item index="/admin/worklogs">工作日志</el-menu-item>
          <el-menu-item index="/admin/plans">计划总结</el-menu-item>
          <el-menu-item index="/admin/schedules">课程表</el-menu-item>
          <el-menu-item index="/admin/activities">班级活动</el-menu-item>
          <el-menu-item index="/admin/talks">师生谈心</el-menu-item>
          <el-menu-item index="/admin/return-records">返校记录</el-menu-item>
          <el-menu-item index="/admin/performances">学生表现</el-menu-item>
          <el-menu-item index="/admin/student-comments">学生评语</el-menu-item>
          <el-menu-item index="/admin/reports">班级报告</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="system">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item v-if="isAdmin" index="/admin/users">账号管理</el-menu-item>
          <el-menu-item v-if="isPlatform" index="/admin/schools">学校管理</el-menu-item>
          <el-menu-item v-if="isAdmin" index="/admin/audit-logs">审计日志</el-menu-item>
          <el-menu-item v-if="isAdmin" index="/admin/settings">系统设置</el-menu-item>
        </el-sub-menu>
      </el-menu>

      <!-- 折叠按钮 -->
      <div class="collapse-btn" @click="collapsed = !collapsed">
        <el-icon><component :is="collapsed ? 'Expand' : 'Fold'" /></el-icon>
      </div>
    </el-aside>

    <!-- 右侧主体 -->
    <el-container class="main-container">
      <el-header class="header">
        <div class="header-left">
          <el-icon class="mobile-menu-btn" @click="mobileMenuOpen = true"><Menu /></el-icon>
          <span class="header-breadcrumb">
            <template v-for="(part, i) in breadcrumb" :key="i">
              <span v-if="i > 0" class="breadcrumb-sep">/</span>
              <span :class="{ 'breadcrumb-current': i === breadcrumb.length - 1 }">{{ part }}</span>
            </template>
          </span>
        </div>

        <el-dropdown @command="onCommand" trigger="click">
          <span class="user-chip">
            <el-avatar :size="32" :src="user?.avatar" class="user-avatar">
              {{ user?.name?.[0] }}
            </el-avatar>
            <span class="user-name">{{ user?.name }}</span>
            <el-tag size="small" effect="plain" type="info">{{ roleText }}</el-tag>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="change-password">
                <el-icon><Key /></el-icon>
                修改密码
              </el-dropdown-item>
              <el-dropdown-item command="portal">
                <el-icon><Switch /></el-icon>
                学生端首页
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>
                <el-icon><Back /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
      <footer class="footer">TechHub · code by longbiu</footer>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getUser, clearAuth, isPlatformAdmin, isSchoolAdmin } from '../utils/auth'

document.title = 'TechHub'

const route = useRoute()
const router = useRouter()
const user = computed(() => getUser())
const isAdmin = computed(() => getUser()?.role === 'admin' || isSchoolAdmin() || isPlatformAdmin())
const isPlatform = computed(() => isPlatformAdmin())
const roleText = computed(() => {
  const r = getUser()?.role
  if (r === 'super_admin') return '平台超管'
  if (r === 'school_admin') return '学校管理员'
  if (r === 'teacher') return '教师'
  return '管理员'
})

const collapsed = ref(false)
const mobileMenuOpen = ref(false)

const titles = {
  '/admin/dashboard': '数据看板',
  '/admin/homework': '作业任务',
  '/admin/students': '学生管理',
  '/admin/classrooms': '班级管理',
  '/admin/scores': '成绩管理',
  '/admin/leaves': '考勤管理',
  '/admin/communications': '家校沟通',
  '/admin/resources': '资源管理',
  '/admin/exams': '试卷管理',
  '/admin/seats': '座位表',
  '/admin/worklogs': '工作日志',
  '/admin/plans': '计划总结',
  '/admin/schedules': '课程表',
  '/admin/activities': '班级活动',
  '/admin/talks': '师生谈心',
  '/admin/return-records': '返校记录',
  '/admin/performances': '学生表现',
  '/admin/student-comments': '学生评语',
  '/admin/reports': '班级报告',
  '/admin/users': '账号管理',
  '/admin/schools': '学校管理',
  '/admin/settings': '系统设置'
}

const activeMenu = computed(() => {
  const p = route.path
  if (p.includes('/submissions')) return '/admin/homework'
  return p
})

const breadcrumb = computed(() => {
  const p = route.path
  if (p.includes('/submissions')) return ['在线作业管理', '提交审阅']
  const name = titles[p]
  if (!name) return ['TechHub']
  // 尝试从路由路径推断所属分组
  for (const [key, val] of Object.entries(titles)) {
    if (key === p) return [name]
  }
  return [name]
})

function onCommand(cmd) {
  if (cmd === 'logout') {
    clearAuth()
    router.push('/admin/login')
  } else if (cmd === 'portal') {
    router.push('/')
  } else if (cmd === 'change-password') {
    router.push('/admin/change-password')
  }
}
</script>

<style scoped>
.admin-layout {
  height: 100vh;
  overflow: hidden;
}

/* -------- 侧边栏 -------- */
.aside {
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  color: #e2e8f0;
  overflow-y: auto;
  overflow-x: hidden;
  transition: width 0.25s ease;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
}

.brand {
  height: 60px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  cursor: pointer;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.brand-mark {
  width: 32px;
  height: 32px;
  min-width: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 15px;
}

.brand-text {
  font-weight: 700;
  font-size: 16px;
  color: #fff;
  white-space: nowrap;
  letter-spacing: -0.01em;
}

/* 菜单 */
.menu {
  border-right: none !important;
  flex: 1;
  padding: 8px;
  overflow-y: auto;
  overflow-x: hidden;
}

.menu :deep(.el-menu-item),
.menu :deep(.el-sub-menu__title) {
  border-radius: 8px;
  margin: 2px 0;
  height: 40px;
  line-height: 40px;
  font-size: 13px;
  transition: all 0.15s ease;
}

.menu :deep(.el-menu-item:hover),
.menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
}

.menu :deep(.el-menu-item.is-active) {
  background: var(--brand);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.35);
}

/* 子菜单展开背景 */
.menu :deep(.el-menu) {
  background: rgba(0, 0, 0, 0.15) !important;
  border-radius: 6px;
  margin: 2px 4px;
}

.menu :deep(.el-menu .el-menu-item) {
  padding-left: 56px !important;
  font-size: 13px;
  height: 36px;
  line-height: 36px;
}

.menu :deep(.el-menu .el-menu-item.is-active) {
  background: var(--brand);
}

/* 折叠模式 */
.menu.el-menu--collapse {
  padding: 8px 4px;
  width: 64px;
}

.menu.el-menu--collapse :deep(.el-menu-item),
.menu.el-menu--collapse :deep(.el-sub-menu__title) {
  padding: 0 !important;
  justify-content: center;
}

.menu.el-menu--collapse :deep(.el-sub-menu__title) .el-icon {
  margin: 0;
}

/* 折叠按钮 */
.collapse-btn {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.4);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
  transition: color 0.15s;
  font-size: 18px;
}

.collapse-btn:hover {
  color: rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.04);
}

/* -------- 右侧主体 -------- */
.main-container {
  flex-direction: column;
  overflow: hidden;
}

.header {
  height: 60px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border-light);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
}

.header-left {
  display: flex;
  align-items: center;
}

.header-breadcrumb {
  font-size: 14px;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.breadcrumb-sep {
  color: #d1d5db;
  font-size: 12px;
}

.breadcrumb-current {
  color: var(--text-primary);
  font-weight: 600;
}

/* 用户区 */
.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.user-chip:hover {
  background: #f3f4f6;
}

.user-avatar {
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  font-weight: 600;
}

.user-name {
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
}

/* 内容区 */
.main {
  background: var(--bg-page);
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* -------- 响应式 -------- */
@media (max-width: 1024px) {
  .aside {
    width: 64px !important;
  }
  .brand-text {
    display: none;
  }
  .collapse-btn {
    display: none;
  }
  .menu {
    padding: 8px 4px;
  }
  .menu :deep(.el-menu-item),
  .menu :deep(.el-sub-menu__title) {
    padding: 0 !important;
    justify-content: center;
  }
  .menu :deep(.el-sub-menu__title) .el-icon {
    margin: 0;
  }
}

@media (max-width: 768px) {
  /* 移动端：侧边栏变为抽屉（默认隐藏，点菜单按钮弹出） */
  .aside {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: 220px !important;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    z-index: 2000;
    box-shadow: 4px 0 20px rgba(0, 0, 0, 0.3);
  }
  .aside.mobile-open {
    transform: translateX(0);
  }
  .mobile-mask {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 1999;
  }
  .mobile-menu-btn {
    display: inline-flex;
    font-size: 20px;
    cursor: pointer;
    color: #4b5563;
    margin-right: 8px;
  }
  .header {
    padding: 0 16px;
  }
  .main {
    padding: 12px;
  }
  .user-name {
    display: none;
  }
  .collapse-btn {
    display: none !important;
  }
}

/* 默认隐藏移动端菜单按钮 */
.mobile-menu-btn {
  display: none;
}

.footer {
  text-align: center;
  color: #9ca3af;
  font-size: 12px;
  padding: 20px;
}
</style>