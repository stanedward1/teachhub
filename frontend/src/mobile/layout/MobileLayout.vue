<template>
  <div class="mobile-layout">
    <van-nav-bar :title="title" fixed placeholder right-text="退出" @click-right="onLogout" />
    <div class="mobile-content">
      <router-view />
    </div>
    <van-tabbar route :fixed="true" :placeholder="true" active-color="#2563eb">
      <van-tabbar-item replace to="/m/home" icon="home-o">首页</van-tabbar-item>
      <van-tabbar-item replace to="/m/checkin" icon="clock-o">考勤</van-tabbar-item>
      <van-tabbar-item replace to="/m/students" icon="friends-o">学生</van-tabbar-item>
      <van-tabbar-item replace to="/m/record" icon="edit">记录</van-tabbar-item>
      <van-tabbar-item replace to="/m/leaves" icon="notes-o">请假</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { showConfirmDialog } from 'vant'
import { useLogout } from '../../composables/useLogout'

const route = useRoute()
const logout = useLogout()

/** 退出登录：二次确认后撤销服务端刷新令牌、清理本地登录态并跳回移动端登录页 */
async function onLogout() {
  try {
    await showConfirmDialog({
      title: '退出登录',
      message: '确定要退出当前账号吗？',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
  } catch {
    // 用户点击取消，静默返回
    return
  }
  logout('/m/login')
}

const title = computed(() => {
  const map = {
    '/m/home': '首页',
    '/m/checkin': '考勤打卡',
    '/m/attendance-stats': '出勤统计',
    '/m/students': '学生速查',
    '/m/record': '快捷记录',
    '/m/leaves': '请假管理',
  }
  if (route.path.startsWith('/m/students/')) return '学生画像'
  return map[route.path] || 'TeachHub'
})
</script>

<style scoped>
.mobile-layout {
  min-height: 100vh;
  background: #f7f8fa;
}
.mobile-content {
  padding-bottom: 12px;
}
</style>
