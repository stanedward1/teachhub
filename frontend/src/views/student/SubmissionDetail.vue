<template>
  <div v-if="item">
    <el-page-header content="提交详情" @back="$router.back()" class="mb" />
    <div class="page-card">
      <div class="hd">
        <h2 class="page-title">{{ item.assignment_title || '作业提交' }}</h2>
        <el-tag :type="item.is_excellent ? 'success' : 'info'" size="small">
          {{ item.is_excellent ? '优秀作品' : '已提交' }}
        </el-tag>
      </div>
      <p class="page-subtitle">提交时间：{{ item.created_at }}</p>

      <!-- 评优评语 -->
      <div v-if="item.is_excellent && item.excellent_note" class="note-box">
        <el-icon><Star /></el-icon>
        <span>评优评语：{{ item.excellent_note }}</span>
      </div>

      <!-- 教师点评（批改评语，含分数） -->
      <div class="teacher-panel">
        <div class="tp-title">
          <el-icon><ChatDotRound /></el-icon>
          教师点评（{{ item.comments?.length || 0 }}）
        </div>
        <div v-if="item.comments?.length" class="tp-list">
          <div v-for="c in item.comments" :key="c.id" class="tp-item">
            <el-avatar :size="28">{{ c.teacher_name?.[0] || '师' }}</el-avatar>
            <div class="tp-body">
              <div class="tp-head">
                <span class="tp-name">{{ c.teacher_name }}</span>
                <el-tag v-if="c.score != null" size="small" type="warning">{{ c.score }} 分</el-tag>
                <span class="tp-time">{{ c.created_at }}</span>
              </div>
              <div class="tp-content">{{ c.content }}</div>
            </div>
          </div>
        </div>
        <div v-else class="tp-empty">教师暂未点评</div>
      </div>

      <!-- AI 批改建议（仅供参考，以教师评语为准） -->
      <AiGradingPanel :ai="item.ai_grading" />

      <el-divider />
      <h4 class="sec-title">我的作业内容</h4>
      <Markdown :content="item.content || ''" />
      <div v-if="item.filepath" class="attach">
        附件：
        <a :href="'/uploads/' + item.filepath" target="_blank">
          {{ item.filename || '下载附件' }}
        </a>
      </div>
    </div>

    <div v-if="item.is_excellent" class="page-card excellent-entry">
      <el-button type="primary" plain @click="goExcellent">
        <el-icon><Trophy /></el-icon> 查看优秀作品详情（含互评）
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Markdown from '../../components/Markdown.vue'
import AiGradingPanel from '../../components/AiGradingPanel.vue'
import { homeworkApi } from '../../api'

const route = useRoute()
const router = useRouter()
const item = ref(null)

onMounted(load)

async function load() {
  item.value = await homeworkApi.submissionDetail(route.params.id)
}

function goExcellent() {
  if (item.value.excellent_id) {
    router.push(`/excellent/${item.value.excellent_id}`)
  }
}
</script>

<style scoped>
.mb {
  margin-bottom: 16px;
}
.hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.note-box {
  margin-top: 12px;
  padding: 10px 14px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  color: #92400e;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.teacher-panel {
  margin-top: 12px;
  padding: 12px 14px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
}
.tp-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #1e40af;
  margin-bottom: 10px;
}
.tp-item {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed #dbeafe;
}
.tp-item:last-child {
  border-bottom: none;
}
.tp-body {
  flex: 1;
}
.tp-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tp-name {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.tp-time {
  font-size: 12px;
  color: #9ca3af;
}
.tp-content {
  font-size: 14px;
  color: #111827;
  margin-top: 2px;
  white-space: pre-wrap;
}
.tp-empty {
  font-size: 13px;
  color: #9ca3af;
  padding: 6px 0;
}
.sec-title {
  margin: 0 0 8px;
}
.attach {
  margin-top: 12px;
  font-size: 13px;
  color: #2563eb;
}
.excellent-entry {
  margin-top: 16px;
}
</style>
