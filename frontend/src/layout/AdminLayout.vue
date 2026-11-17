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
    <!-- 头像上传：顶栏菜单「更换头像」触发这个隐藏的 file input -->
    <input
      ref="avatarInput"
      type="file"
      accept="image/jpeg,image/png,image/gif,image/webp"
      class="avatar-input"
      @change="onAvatarChange"
    />
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '../api'
import { useAuthStore } from '../stores/auth'
import { useLogout } from '../composables/useLogout'
import AdminSidebar from './admin/AdminSidebar.vue'
import AdminHeader from './admin/AdminHeader.vue'
import { MENU, filterMenuByRole, resolveActiveMenu, resolveBreadcrumb } from './admin/menuConfig.js'
import { isStaffRole, ROLE_LABELS } from '../utils/roles'

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
  // 管理端头部：仅识别三种教职角色，学生/未知角色回退「管理员」（与原实现逐字一致）
  return isStaffRole(r) ? ROLE_LABELS[r] : '管理员'
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
  } else if (cmd === 'change-avatar') {
    // 后端 `POST /api/auth/avatar` 本来就对任意登录用户开放（学生/教师均可传
    // 自己的头像），但此前只有学生端 Profile 有入口，管理端顶栏头像永远是空的。
    avatarInput.value?.click()
  }
}

/* -------- 更换头像（教师 / 管理员） -------- */
const avatarInput = ref(null)
const AVATAR_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
const AVATAR_MAX = 2 * 1024 * 1024

async function onAvatarChange(e) {
  const file = e.target.files?.[0]
  // 立刻清空：否则连续选同一个文件不会再触发 change（浏览器按值比较）
  e.target.value = ''
  if (!file) return
  // 前端先挡一层只是为了省一次请求；真正的权威校验在 uploads_service.save_avatar
  // （扩展名白名单 → 400，超过 2MB → 413）
  if (!AVATAR_TYPES.includes(file.type)) {
    return ElMessage.error('仅支持 JPG/PNG/GIF/WebP 格式的图片')
  }
  if (file.size > AVATAR_MAX) {
    return ElMessage.error('头像文件不能超过 2MB')
  }
  const fd = new FormData()
  fd.append('file', file)
  try {
    const res = await authApi.uploadAvatar(fd)
    if (res?.avatar) {
      // 必须走 setAuth 回写：顶栏 el-avatar 读的是 auth.user.avatar，
      // 同时 localStorage 里的用户副本也要一起更新，否则刷新后又变回首字
      auth.setAuth(auth.token, { ...auth.user, avatar: res.avatar })
    }
    ElMessage.success('头像更新成功')
  } catch (e) {
    // 错误提示由 request.js 的全局拦截器统一弹出（含 400/413 的具体文案）
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

/* 隐藏的头像选择器：只由顶栏菜单触发 click() */
.avatar-input {
  display: none;
}
</style>
