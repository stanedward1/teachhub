<template>
  <el-container class="admin-layout">
    <!-- 移动端遮罩 -->
    <div v-if="mobileMenuOpen" class="mobile-mask" @click="mobileMenuOpen = false"></div>

    <!-- 侧边栏：el-aside 外壳保留在父组件，仅内容交由 AdminSidebar 渲染 -->
    <el-aside
      :width="collapsed ? '64px' : '220px'"
      class="aside"
      :class="{ 'mobile-open': mobileMenuOpen }"
    >
      <AdminSidebar
        v-model:collapsed="collapsed"
        :items="menuItems"
        :active-menu="activeMenu"
        @select="mobileMenuOpen = false"
      />
    </el-aside>

    <!-- 右侧主体 -->
    <el-container class="main-container">
      <!-- el-header 外壳保留在父组件，仅内容交由 AdminHeader 渲染 -->
      <el-header class="header">
        <AdminHeader
          :breadcrumb="breadcrumb"
          :user="user"
          :role-text="roleText"
          @open-menu="mobileMenuOpen = true"
          @command="onCommand"
        />
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
      <footer class="footer">TeachHub · code by longbiu</footer>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useLogout } from '../composables/useLogout'
import AdminSidebar from './admin/AdminSidebar.vue'
import AdminHeader from './admin/AdminHeader.vue'
import { MENU, filterMenuByRole, resolveActiveMenu, resolveBreadcrumb } from './admin/menuConfig.js'

document.title = 'TeachHub'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const logout = useLogout()
const user = computed(() => auth.user)
const isAdmin = computed(() => auth.isSchoolAdmin || auth.isPlatformAdmin)
const isPlatform = computed(() => auth.isPlatformAdmin)
const roleText = computed(() => {
  const r = auth.user?.role
  if (r === 'super_admin') return '平台超管'
  if (r === 'school_admin') return '学校管理员'
  if (r === 'teacher') return '教师'
  return '管理员'
})

const collapsed = ref(false)
const mobileMenuOpen = ref(false)

const activeMenu = computed(() => resolveActiveMenu(route.path))
const breadcrumb = computed(() => resolveBreadcrumb(route.path))
const menuItems = computed(() =>
  filterMenuByRole(MENU, {
    isAdmin: isAdmin.value,
    isPlatform: isPlatform.value,
    // 审计日志对班主任可见（need: 'head_teacher'），与后端 _visible_audit_class_ids 同源
    isHeadTeacher: auth.isHeadTeacher,
  })
)

function onCommand(cmd) {
  if (cmd === 'logout') {
    // 撤销服务端刷新令牌后再清理本地登录态
    logout('/admin/login')
  } else if (cmd === 'portal') {
    // 学生端首页需以学生身份登录：先撤销管理端刷新令牌，再跳学生端登录页
    logout('/login')
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

/* 内容区 */
.main {
  background: var(--bg-page);
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

/* -------- 响应式 -------- */
@media (max-width: 1024px) {
  .aside {
    width: 64px !important;
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
  .header {
    padding: 0 16px;
  }
  .main {
    padding: 12px;
  }
}

.footer {
  text-align: center;
  color: #9ca3af;
  font-size: 12px;
  padding: 20px;
}
</style>
