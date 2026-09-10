<template>
  <div>
    <h2 class="page-title">编程练习</h2>
    <p class="page-subtitle">热门在线评测平台与 C 语言入门教程，助你提升编程能力</p>

    <el-row :gutter="16">
      <el-col :span="12">
        <div class="page-card">
          <h3 class="sec-title"><el-icon><Monitor /></el-icon> 推荐 OJ 平台</h3>
          <div class="link-list">
            <a v-for="o in data.oj" :key="o.name" :href="o.url" target="_blank" class="link-item">
              <div>
                <div class="l-name">{{ o.name }}</div>
                <div class="l-desc">{{ o.desc }}</div>
              </div>
              <el-icon><Right /></el-icon>
            </a>
          </div>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="page-card">
          <h3 class="sec-title"><el-icon><Reading /></el-icon> C 语言入门教程</h3>
          <div class="link-list">
            <a v-for="t in data.tutorials" :key="t.name" :href="t.url" target="_blank" class="link-item">
              <div>
                <div class="l-name">{{ t.name }}</div>
                <div class="l-desc">{{ t.desc }}</div>
              </div>
              <el-icon><Right /></el-icon>
            </a>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { metaApi } from '../../api'

const data = ref({ oj: [], tutorials: [] })

onMounted(async () => {
  try {
    data.value = await metaApi.practice()
  } catch (e) {
    console.error('[Practice] 加载练习推荐失败:', e)
  }
})
</script>

<style scoped>
.sec-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  color: #111827;
}
.link-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.link-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border: 1px solid #eef1f6;
  border-radius: 10px;
  text-decoration: none;
  color: inherit;
  transition: all 0.2s;
}
.link-item:hover {
  border-color: #2563eb;
  background: #eff6ff;
}
.l-name {
  font-weight: 600;
  color: #111827;
}
.l-desc {
  font-size: 13px;
  color: #6b7280;
  margin-top: 2px;
}
</style>
