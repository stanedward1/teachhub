<template>
  <div class="error-page">
    <div class="error-code">403</div>
    <p class="error-desc">无权访问该页面</p>
    <el-button type="primary" @click="goBack">返回</el-button>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

function goBack() {
  // 有历史则回上一页；直达链接（无历史）时退回首页
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/')
  }
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
  color: var(--el-color-warning);
  letter-spacing: 4px;
}
.error-desc {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
}
</style>
