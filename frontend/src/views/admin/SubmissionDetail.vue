<template>
  <div>
    <el-page-header
      :content="`${submission?.student_name || ''} 的作业`"
      @back="$router.back()"
      style="margin-bottom: 16px"
    />

    <div class="page-card" v-if="submission">
      <!-- 提交信息 -->
      <div class="meta-row">
        <el-tag size="small" :type="submission.is_excellent ? 'success' : 'info'">
          {{ submission.is_excellent ? '优秀作品' : '普通提交' }}
        </el-tag>
        <span class="meta-time">提交时间：{{ submission.created_at }}</span>
        <a
          v-if="submission.filepath"
          :href="'/uploads/' + submission.filepath"
          target="_blank"
          class="meta-file"
        >
          📎 {{ submission.filename || '下载附件' }}
        </a>
      </div>

      <!-- 完整作业内容 -->
      <div class="content-full">
        <div style="font-weight: 500; margin-bottom: 10px; color: #303133">作业内容</div>
        <div v-if="submission.content" class="md-wrap">
          <Markdown :content="submission.content" />
        </div>
        <div v-else style="color: #9ca3af">（仅上传附件，无文字内容）</div>
      </div>

      <!-- AI 批改建议（与教师点评并列，不互相覆盖）；未批改时给出触发入口 -->
      <div v-if="submission" class="ai-section">
        <div class="ai-head">
          <span class="ai-title">AI 批改建议</span>
          <el-tag v-if="ai" size="small" :type="aiStatusType(ai.status)">
            {{ aiStatusText(ai.status) }}
          </el-tag>
          <el-tag v-if="ai && ai.score != null" size="small" type="warning">
            {{ ai.score }} 分
          </el-tag>
          <span v-if="ai && ai.model" class="ai-model">{{ ai.model }}</span>
          <el-button
            v-if="ai && ai.is_excellent_candidate && !submission.is_excellent"
            link
            type="primary"
            size="small"
            :loading="accepting"
            @click="acceptAiExcellent"
          >
            采纳为优秀作品
          </el-button>
          <el-button link type="primary" size="small" :loading="aiRunning" @click="runAiGrading">
            {{ ai ? '重新批改' : 'AI 批改' }}
          </el-button>
        </div>
        <div class="ai-tip">AI 生成，仅供参考，以教师评语为准</div>

        <div v-if="!ai" class="ai-text ai-muted">尚未批改，点击上方「AI 批改」发起。</div>
        <template v-else-if="ai.status === 'success'">
          <div v-if="ai.summary" class="ai-block">
            <div class="ai-label">总评</div>
            <div class="ai-text">{{ ai.summary }}</div>
          </div>
          <div v-if="ai.strengths" class="ai-block">
            <div class="ai-label">亮点</div>
            <div class="ai-text">{{ ai.strengths }}</div>
          </div>
          <div v-if="ai.improvements" class="ai-block">
            <div class="ai-label">改进建议</div>
            <div class="ai-text">{{ ai.improvements }}</div>
          </div>
          <div v-if="ai.excellent_reason" class="ai-block">
            <div class="ai-label">推荐理由</div>
            <div class="ai-text">{{ ai.excellent_reason }}</div>
          </div>
          <div v-if="ai.attachment_used" class="ai-attach">附件：{{ ai.attachment_used }}</div>
        </template>
        <div v-else-if="ai.status === 'pending'" class="ai-text ai-muted">批改中，请稍后刷新…</div>
        <div v-else class="ai-text">
          批改未完成<template v-if="ai.error">：{{ ai.error }}</template>
        </div>
      </div>

      <!-- 教师点评区 -->
      <div class="comments-section">
        <div style="font-weight: 500; margin-bottom: 12px; color: #303133">
          教师点评
          <el-tag
            v-if="submission.comments?.length"
            size="small"
            type="primary"
            style="margin-left: 8px"
          >
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
              <el-tag
                v-if="c.score !== null && c.score !== undefined"
                size="small"
                :type="scoreType(c.score)"
              >
                {{ c.score }} 分
              </el-tag>
              <span class="comment-time">{{ c.created_at }}</span>
              <el-button
                v-if="c.teacher_id === currentUser?.id || isAdmin"
                link
                type="danger"
                size="small"
                @click="removeComment(c)"
                >删除</el-button
              >
            </div>
            <div class="comment-content">{{ c.content }}</div>
          </div>
        </div>

        <!-- 添加点评 -->
        <div class="comment-form">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="3"
            placeholder="输入点评内容..."
          />
          <div class="comment-form-actions">
            <el-input-number
              v-model="form.score"
              :min="0"
              :max="100"
              placeholder="评分(可选)"
              style="width: 160px"
            />
            <el-button type="primary" :loading="saving" @click="submitComment">提交点评</el-button>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!loading" class="empty">提交不存在或已被删除</div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
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
      score: form.score,
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

// ---------------- AI 批改 ----------------
// 批改为教师手动触发（学生提交不会自动批改），此处提供单份触发/重批入口
const ai = computed(() => submission.value?.ai_grading || null)
const aiRunning = ref(false)
const accepting = ref(false) // 采纳 AI 推荐提交中（防重复提交）

function aiStatusText(status) {
  if (status === 'success') return '已批改'
  if (status === 'pending') return '批改中'
  return '未完成'
}

function aiStatusType(status) {
  if (status === 'success') return 'success'
  if (status === 'pending') return 'warning'
  return 'info'
}

async function runAiGrading() {
  aiRunning.value = true
  try {
    await homeworkApi.aiGradeSubmission(route.params.submissionId)
    ElMessage.success('已发起 AI 批改，稍后刷新查看结果')
    // 批改在后台线程执行，延迟刷新以拿到最新状态
    setTimeout(load, 1500)
  } catch (e) {
    // 失败原因（总开关未开启 / 未配凭证 / 额度耗尽）由全局拦截器提示
  } finally {
    aiRunning.value = false
  }
}

/** 采纳 AI 推荐：复用既有评优链路，标记来源为 ai_recommended */
async function acceptAiExcellent() {
  if (accepting.value) return // 防重复提交：并发请求会把「已入选」预检跑在写入之前，撞唯一索引报 409
  accepting.value = true
  try {
    await ElMessageBox.confirm('将该提交采纳为班级优秀作品？采纳后学生端即可看到。', '确认采纳', {
      type: 'info',
    })
    await homeworkApi.markExcellent(route.params.submissionId, {
      note: submission.value?.ai_grading?.excellent_reason || 'AI 推荐采纳',
      from_ai: true,
    })
    ElMessage.success('已采纳为优秀作品')
    load()
  } catch (e) {
    // 用户取消确认框或接口失败（失败原因由全局拦截器提示）
  } finally {
    accepting.value = false
  }
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
.meta-time {
  color: #6b7280;
  font-size: 13px;
}
.meta-file {
  color: #2563eb;
  font-size: 13px;
}
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
.md-wrap :deep(.md-body) img {
  max-width: 100%;
}
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
.comment-avatar {
  flex-shrink: 0;
  background: #4f46e5;
}
.comment-body {
  flex: 1;
}
.comment-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}
.comment-teacher {
  font-weight: 500;
  color: #111827;
  font-size: 14px;
}
.comment-time {
  color: #9ca3af;
  font-size: 12px;
}
.comment-content {
  color: #374151;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}
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
.empty {
  text-align: center;
  color: #9ca3af;
  padding: 60px 0;
}
/* AI 批改区块：与教师点评（蓝色）在视觉上明确区分，强调「仅供参考」 */
.ai-section {
  background: #f5f3ff;
  border: 1px solid #ddd6fe;
  border-radius: 10px;
  padding: 16px 20px;
  margin-bottom: 20px;
}
.ai-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.ai-title {
  font-weight: 600;
  color: #5b21b6;
  font-size: 14px;
}
.ai-model {
  font-size: 12px;
  color: #9ca3af;
}
.ai-tip {
  font-size: 12px;
  color: #9ca3af;
  margin: 6px 0 12px;
}
.ai-block {
  margin-bottom: 10px;
}
.ai-label {
  font-size: 12px;
  font-weight: 600;
  color: #6d28d9;
  margin-bottom: 4px;
}
.ai-text {
  font-size: 14px;
  color: #374151;
  line-height: 1.7;
  white-space: pre-wrap;
}
.ai-muted {
  color: #9ca3af;
}
.ai-attach {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 8px;
}
</style>
