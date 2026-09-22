<template>
  <div v-if="item">
    <el-page-header content="优秀作品详情" @back="$router.back()" class="mb" />
    <div class="page-card">
      <div class="head">
        <div class="work-title-wrap">
          <el-icon class="title-icon"><Document /></el-icon>
          <h3 class="work-title">{{ item.assignment_title || '优秀作业' }}</h3>
        </div>
        <div class="author">
          <el-avatar :size="28" :src="item.student_avatar">{{ item.student_name?.[0] }}</el-avatar>
          <span class="author-name">{{ item.student_name }}</span>
          <span class="author-cls">{{ item.class_name }}</span>
        </div>
      </div>
      <div v-if="item.note" class="teacher-note">
        <el-icon><Star /></el-icon> 评选评语：{{ item.note }}
      </div>
      <div v-if="item.teacher_comments?.length" class="teacher-comments">
        <div class="tc-title">批改评语（{{ item.teacher_comments.length }}）</div>
        <div v-for="tc in item.teacher_comments" :key="tc.id" class="tc-item">
          <el-avatar :size="28">{{ tc.teacher_name?.[0] || '师' }}</el-avatar>
          <div class="tc-body">
            <div class="tc-head">
              <span class="tc-name">{{ tc.teacher_name }}</span>
              <el-tag v-if="tc.score != null" size="small" type="warning">{{ tc.score }} 分</el-tag>
              <span class="tc-time">{{ tc.created_at }}</span>
            </div>
            <div class="tc-content">{{ tc.content }}</div>
          </div>
        </div>
      </div>
      <!-- AI 批改意见（与教师批改评语并列展示，仅供参考） -->
      <AiGradingPanel :ai="item.ai_grading" />
      <el-divider />
      <h4>作业内容</h4>
      <Markdown :content="item.submission?.content || ''" />
      <div v-if="item.submission?.filepath" class="attach">
        附件：
        <a :href="'/uploads/' + item.submission.filepath" target="_blank">
          {{ item.submission.filename || '下载附件' }}
        </a>
      </div>
    </div>

    <div class="page-card comment-card">
      <h3>评论互动（{{ item.comments?.length || 0 }}）</h3>
      <div class="comment-input">
        <el-input v-model="comment" placeholder="写下你的评论…" />
        <el-button type="primary" @click="submit">发表</el-button>
      </div>
      <div v-if="item.comments?.length" class="comments">
        <div v-for="c in item.comments" :key="c.id" class="c-item">
          <el-avatar :size="32" :src="c.user_avatar">{{ c.user_name?.[0] }}</el-avatar>
          <div>
            <div class="c-name">{{ c.user_name }}</div>
            <div class="c-content">{{ c.content }}</div>
          </div>
        </div>
      </div>
      <div v-else class="empty">还没有评论，快来抢沙发～</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import Markdown from '../../components/Markdown.vue'
import AiGradingPanel from '../../components/AiGradingPanel.vue'
import { homeworkApi } from '../../api'

const route = useRoute()
const item = ref(null)
const comment = ref('')

onMounted(load)

async function load() {
  item.value = await homeworkApi.excellentDetail(route.params.id)
}

async function submit() {
  if (!comment.value.trim()) return ElMessage.warning('评论不能为空')
  await homeworkApi.addComment(route.params.id, { content: comment.value })
  comment.value = ''
  ElMessage.success('评论成功')
  load()
}
</script>

<style scoped>
.mb {
  margin-bottom: 16px;
}
.head {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.work-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title-icon {
  color: #2563eb;
  font-size: 20px;
}
.work-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}
.author {
  display: flex;
  align-items: center;
  gap: 8px;
}
.author-name {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.author-cls {
  font-size: 12px;
  color: #9ca3af;
}
.teacher-note {
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
.teacher-comments {
  margin-top: 12px;
  padding: 12px 14px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
}
.tc-title {
  font-size: 13px;
  font-weight: 600;
  color: #1e40af;
  margin-bottom: 10px;
}
.tc-item {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px dashed #dbeafe;
}
.tc-item:last-child {
  border-bottom: none;
}
.tc-body {
  flex: 1;
}
.tc-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tc-name {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.tc-time {
  font-size: 12px;
  color: #9ca3af;
}
.tc-content {
  font-size: 14px;
  color: #111827;
  margin-top: 2px;
}
.attach {
  margin-top: 12px;
  font-size: 13px;
  color: #2563eb;
}
.comment-card {
  margin-top: 16px;
}
.comment-card h3 {
  margin: 0 0 12px;
}
.comment-input {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
.comments {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.c-item {
  display: flex;
  gap: 10px;
}
.c-name {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.c-content {
  font-size: 14px;
  color: #111827;
  margin-top: 2px;
}
.empty {
  color: #9ca3af;
  text-align: center;
  padding: 30px 0;
}
</style>
