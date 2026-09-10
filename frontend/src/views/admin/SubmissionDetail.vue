<template>
  <div>
    <el-page-header :content="`${submission?.student_name || ''} 的作业`" @back="$router.back()" style="margin-bottom: 16px" />

    <div class="page-card" v-if="submission">
      <!-- 提交信息 -->
      <div class="meta-row">
        <el-tag size="small" :type="submission.is_excellent ? 'success' : 'info'">
          {{ submission.is_excellent ? '优秀作品' : '普通提交' }}
        </el-tag>
        <span class="meta-time">提交时间：{{ submission.created_at }}</span>
        <a v-if="submission.filepath" :href="'/uploads/' + submission.filepath" target="_blank" class="meta-file">
          📎 {{ submission.filename || '下载附件' }}
        </a>
      </div>

      <!-- 完整作业内容 -->
      <div class="content-full">
        <div style="font-weight: 500; margin-bottom: 10px; color: #303133;">作业内容</div>
        <div v-if="submission.content" class="md-wrap">
          <Markdown :content="submission.content" />
        </div>
        <div v-else style="color: #9ca3af;">（仅上传附件，无文字内容）</div>
      </div>

      <!-- 教师点评区 -->
      <div class="comments-section">
        <div style="font-weight: 500; margin-bottom: 12px; color: #303133;">
          教师点评
          <el-tag v-if="submission.comments?.length" size="small" type="primary" style="margin-left: 8px">
            {{ submission.comments.length }} 条
          </el-tag>
        </div>

        <div v-if="!submission.comments?.length" class="empty-comment">
          暂无点评，写下第一条评语吧
        </div>

        <div v-for="c in submission.comments" :key="c.id" class="comment-item">
          <el-avatar :size="32" class="comment-avatar">{{ c.teacher_name?.[0] || '师' }}</el-avatar>
          <div class="comment-body">
            <div class="comment-head">
              <span class="comment-teacher">{{ c.teacher_name }}</span>
              <el-tag v-if="c.score !== null && c.score !== undefined" size="small" :type="scoreType(c.score)">
                {{ c.score }} 分
              </el-tag>
              <span class="comment-time">{{ c.created_at }}</span>
              <el-button
v-if="c.teacher_id === currentUser?.id || isAdmin"
                link type="danger" size="small" @click="removeComment(c)">删除</el-button>
            </div>
            <div class="comment-content">{{ c.content }}</div>
          </div>
        </div>

        <!-- 添加点评 -->
        <div class="comment-form">
          <el-input v-model="form.content" type="textarea" :rows="3" placeholder="输入点评内容..." />
          <div class="comment-form-actions">
            <el-input-number v-model="form.score" :min="0" :max="100" placeholder="评分(可选)" style="width: 160px" />
            <el-button type="primary" :loading="saving" @click="submitComment">提交点评</el-button>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!loading" class="empty">提交不存在或已被删除</div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import Markdown from '../../components/Markdown.vue'
import { homeworkApi } from '../../api'
import { getUser, isSchoolAdmin, isPlatformAdmin } from '../../utils/auth'

const route = useRoute()
const submission = ref(null)
const loading = ref(true)
const saving = ref(false)
const form = reactive({ content: '', score: null })
const currentUser = getUser()
// 学校管理员 / 平台超管可删除任意点评
const isAdmin = isSchoolAdmin() || isPlatformAdmin()

onMounted(load)

async function load() {
  loading.value = true
  try {
    submission.value = await homeworkApi.submissionDetail(route.params.submissionId)
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function scoreType(s) {
  if (s >= 90) return 'success'
  if (s >= 60) return 'primary'
  return 'danger'
}

async function submitComment() {
  if (!form.content.trim()) return ElMessage.warning('请输入点评内容')
  saving.value = true
  try {
    await homeworkApi.addSubmissionComment(route.params.submissionId, {
      content: form.content,
      score: form.score
    })
    ElMessage.success('点评成功')
    form.content = ''
    form.score = null
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function removeComment(c) {
  await ElMessageBox.confirm('确定删除这条点评吗？', '提示', { type: 'warning' })
  await homeworkApi.deleteSubmissionComment(route.params.submissionId, c.id)
  ElMessage.success('已删除')
  load()
}
</script>

<style scoped>
.meta-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.meta-time { color: #6b7280; font-size: 13px; }
.meta-file { color: #2563eb; font-size: 13px; }
.content-full {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 20px;
}
.md-wrap :deep(.md-body) {
  font-size: 15px;
  line-height: 1.8;
}
.md-wrap :deep(.md-body) img { max-width: 100%; }
.comments-section {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 20px;
}
.empty-comment {
  color: #9ca3af;
  font-size: 13px;
  padding: 16px 0;
  text-align: center;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 12px;
}
.comment-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #f3f4f6;
}
.comment-avatar { flex-shrink: 0; background: #4f46e5; }
.comment-body { flex: 1; }
.comment-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}
.comment-teacher { font-weight: 500; color: #111827; font-size: 14px; }
.comment-time { color: #9ca3af; font-size: 12px; }
.comment-content { color: #374151; font-size: 14px; line-height: 1.6; white-space: pre-wrap; }
.comment-form {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #e5e7eb;
}
.comment-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
  align-items: center;
}
.empty { text-align: center; color: #9ca3af; padding: 60px 0; }
</style>
