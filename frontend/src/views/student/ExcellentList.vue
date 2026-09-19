<template>
  <div>
    <h2 class="page-title">优秀作品</h2>
    <p class="page-subtitle">老师评选的优秀作业，互相学习、评论互动</p>

    <StateView
      :loading="loading"
      :error="error"
      :empty="!items.length"
      :rows="5"
      :columns="3"
      empty-description="暂无优秀作品"
      @retry="load"
    >
      <div class="grid">
        <el-card
          v-for="e in items"
          :key="e.id"
          class="card"
          shadow="hover"
          @click="$router.push(`/excellent/${e.id}`)"
        >
          <!-- 作品标题（任务维度） -->
          <div class="work-title">
            <el-icon class="title-icon"><Document /></el-icon>
            <span>{{ e.assignment_title || '优秀作业' }}</span>
          </div>

          <!-- 作品内容预览（核心） -->
          <div class="work-preview">{{ preview(e.submission?.content) }}</div>

          <!-- 作者与互动（次要信息） -->
          <div class="work-footer">
            <div class="author">
              <el-avatar :size="22" :src="e.student_avatar">{{ e.student_name?.[0] }}</el-avatar>
              <span class="author-name">{{ e.student_name }}</span>
              <span class="author-cls">{{ e.class_name }}</span>
            </div>
            <div class="work-meta">
              <span v-if="e.note" class="note" :title="e.note">
                <el-icon><Star /></el-icon>{{ e.note }}
              </span>
              <span class="comments"
                ><el-icon><ChatDotRound /></el-icon>{{ e.comment_count }}</span
              >
            </div>
          </div>
        </el-card>
      </div>
    </StateView>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import StateView from '../../components/StateView.vue'
import { homeworkApi } from '../../api'

const items = ref([])
const loading = ref(true)
const error = ref(false)

async function load() {
  loading.value = true
  error.value = false
  try {
    const res = await homeworkApi.excellent()
    items.value = res.items
  } catch (e) {
    error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)

// 将 Markdown 正文转为纯文本预览（突出作品内容本身）
function preview(md) {
  if (!md) return '（仅附件）'
  return md
    .replace(/```[\s\S]*?```/g, (m) => m.replace(/```\w*\n?/g, '').trim())
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '[图片]')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[#>*`~|]/g, '')
    .replace(/\n+/g, ' ')
    .trim()
    .slice(0, 140)
}
</script>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.card {
  cursor: pointer;
  border-radius: 12px;
  transition: border-color 0.2s;
}
.card:hover {
  border-color: #2563eb;
}
.work-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 12px;
}
.title-icon {
  color: #2563eb;
}
.work-preview {
  background: #f8fafc;
  border: 1px solid #eef1f6;
  border-radius: 8px;
  padding: 12px 14px;
  font-family: 'JetBrains Mono', 'SFMono-Regular', Consolas, 'Courier New', monospace;
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
  min-height: 72px;
  max-height: 120px;
  overflow: hidden;
  word-break: break-all;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
}
.work-footer {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
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
.work-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  color: #9ca3af;
  font-size: 12px;
}
.work-meta .note {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: #b45309;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.work-meta .comments {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.empty {
  text-align: center;
  color: #9ca3af;
  padding: 60px 0;
}
</style>
