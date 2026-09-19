<template>
  <div class="student-layout">
    <header class="navbar">
      <div class="nav-inner">
        <div class="logo" @click="$router.push('/homework')">
          <span class="logo-mark">S</span>
          <span class="logo-text">StudyHub</span>
        </div>
        <nav class="nav-links">
          <router-link to="/homework" active-class="active">我的作业</router-link>
          <router-link to="/excellent" active-class="active">优秀作品</router-link>
          <router-link to="/my-submissions" active-class="active">我的提交</router-link>
          <router-link to="/practice" active-class="active">编程练习</router-link>
        </nav>
        <el-dropdown @command="onCommand">
          <span class="user-chip">
            <el-avatar :size="30" :src="user?.avatar">{{ user?.name?.[0] }}</el-avatar>
            <span class="uname">{{ user?.name }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人资料</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>
    <main class="content">
      <router-view />
    </main>
    <footer class="footer">StudyHub · code by longbiu</footer>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useLogout } from '../composables/useLogout'

document.title = 'StudyHub'

const router = useRouter()
const auth = useAuthStore()
const logout = useLogout()
const user = computed(() => auth.user)

function onCommand(cmd) {
  if (cmd === 'logout') {
    // 撤销服务端刷新令牌后再清理本地登录态
    logout('/login')
  } else if (cmd === 'profile') {
    router.push('/profile')
  }
}
</script>

<style scoped>
.student-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.navbar {
  background: #fff;
  border-bottom: 1px solid #eef1f6;
  position: sticky;
  top: 0;
  z-index: 10;
}
.nav-inner {
  max-width: 1100px;
  margin: 0 auto;
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 32px;
}
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}
.logo-mark {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}
.logo-text {
  font-weight: 700;
  color: #111827;
}
.nav-links {
  display: flex;
  gap: 8px;
  flex: 1;
}
.nav-links a {
  text-decoration: none;
  color: #4b5563;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 14px;
}
.nav-links a:hover {
  background: #f3f4f6;
}
.nav-links a.active {
  color: #2563eb;
  background: #eff6ff;
  font-weight: 600;
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
}
.uname {
  font-size: 14px;
  color: #374151;
}
.content {
  flex: 1;
  max-width: 1100px;
  width: 100%;
  margin: 0 auto;
  padding: 24px 20px;
}
.footer {
  text-align: center;
  color: #9ca3af;
  font-size: 12px;
  padding: 20px;
}

/* -------- 移动端适配 -------- */
@media (max-width: 768px) {
  .nav-inner {
    padding: 0 12px;
    gap: 16px;
  }
  .nav-links {
    gap: 4px;
  }
  .nav-links a {
    padding: 6px 8px;
    font-size: 13px;
  }
  .logo-text {
    display: none;
  }
  .uname {
    display: none;
  }
  .content {
    padding: 16px 12px;
  }
}
@media (max-width: 480px) {
  .nav-links {
    overflow-x: auto;
    white-space: nowrap;
    -webkit-overflow-scrolling: touch;
  }
  .nav-links::-webkit-scrollbar {
    display: none;
  }
}
</style>
