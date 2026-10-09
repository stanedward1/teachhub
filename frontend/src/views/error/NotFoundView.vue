<template>
  <div class="error-page">
    <div class="error-code">404</div>
    <p class="error-desc">页面不存在或已下线</p>
    <el-button type="primary" @click="goHome">返回首页</el-button>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

function goHome() {
  router.push('/')
}
</script>

<style scoped>
.error-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--gap-md);
  background: var(--bg-page);
}
.error-code {
  font-size: 96px;
  font-weight: 700;
  line-height: 1;
  color: var(--el-color-primary);
  letter-spacing: 4px;
}
.error-desc {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
}
</style>
