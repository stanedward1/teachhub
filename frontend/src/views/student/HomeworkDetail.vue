<template>
  <div v-if="assignment">
    <el-page-header content="作业详情" @back="$router.back()" class="mb" />
    <div class="page-card">
      <div class="hd">
        <div>
          <h2 class="page-title">{{ assignment.title }}</h2>
          <p class="page-subtitle">
            {{ assignment.class_name }} · {{ assignment.creator_name }} · 截止
            {{ assignment.deadline || '不限' }}
          </p>
        </div>
        <el-tag :type="submitted ? 'success' : 'warning'">{{
          submitted ? '已提交' : '待提交'
        }}</el-tag>
      </div>
      <el-divider />
      <Markdown :content="assignment.content" />
      <div v-if="assignment.attachments && assignment.attachments.length" class="attach-box">
        <span class="attach-label">任务附件：</span>
        <div v-for="(att, i) in assignment.attachments" :key="i" class="attach-link">
          <el-link type="primary" :href="'/uploads/' + att.filepath" target="_blank">{{
            att.filename
          }}</el-link>
        </div>
      </div>
    </div>

    <div v-if="submitted && submission" class="page-card feedback-card">
      <div class="fb-head">
        <h3>教师反馈</h3>
        <el-tag v-if="submission.is_excellent" type="success" size="small">优秀作品</el-tag>
      </div>
      <div v-if="submission.is_excellent && submission.excellent_note" class="note-box">
        <el-icon><Star /></el-icon>
        <span>评优评语：{{ submission.excellent_note }}</span>
      </div>
      <div class="teacher-panel">
        <div class="tp-title">
          <el-icon><ChatDotRound /></el-icon>
          教师点评（{{ submission.comments?.length || 0 }}）
        </div>
        <div v-if="submission.comments?.length" class="tp-list">
          <div v-for="c in submission.comments" :key="c.id" class="tp-item">
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
        <div v-else class="tp-empty">教师暂未点评，请耐心等待</div>
      </div>
      <!-- AI 批改意见（与教师点评并列展示，仅供参考） -->
      <AiGradingPanel :ai="submission.ai_grading" />
    </div>

    <div class="page-card submit-card">
      <h3>提交作业</h3>
      <MarkdownEditor v-model="content" :rows="8" />
      <div class="upload-row">
        <el-upload :show-file-list="true" :http-request="doUpload" :limit="1">
          <el-button>上传附件</el-button>
        </el-upload>
        <span v-if="filename" class="file-tip">已选择：{{ filename }}</span>
      </div>
      <div class="actions">
        <el-button type="primary" :loading="submitting" @click="submit">提交作业</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import Markdown from '../../components/Markdown.vue'
import MarkdownEditor from '../../components/MarkdownEditor.vue'
import AiGradingPanel from '../../components/AiGradingPanel.vue'
import { homeworkApi, uploadFile } from '../../api'

const route = useRoute()
const assignment = ref(null)
const content = ref('')
const submitted = ref(false)
const submitting = ref(false)
const filepath = ref('')
const filename = ref('')
const submission = ref(null)

onMounted(async () => {
  await load()
})

async function load() {
  const res = await homeworkApi.assignment(route.params.id)
  assignment.value = res
  const subs = await homeworkApi.submissions(route.params.id)
  if (subs.items.length > 0) {
    submitted.value = true
    const s = subs.items[0]
    content.value = s.content || ''
    filepath.value = s.filepath || ''
    filename.value = s.filename || ''
    await loadFeedback(s.id)
  }
}

async function loadFeedback(submissionId) {
  try {
    submission.value = await homeworkApi.submissionDetail(submissionId)
  } catch (e) {
    console.error('[HomeworkDetail] 加载教师反馈失败:', e)
  }
}

async function doUpload({ file }) {
  const res = await uploadFile(file)
  filepath.value = res.filepath
  filename.value = res.filename
  ElMessage.success('附件上传成功')
}

async function submit() {
  if (!content.value.trim() && !filepath.value) {
    return ElMessage.warning('请填写作业内容或上传附件')
  }
  submitting.value = true
  try {
    const res = await homeworkApi.submit(route.params.id, {
      content: content.value,
      filepath: filepath.value,
      filename: filename.value,
    })
    ElMessage.success('提交成功')
    submitted.value = true
    if (res?.id) await loadFeedback(res.id)
  } catch (e) {
    console.error('[HomeworkDetail] 提交作业失败:', e)
  } finally {
    submitting.value = false
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
  align-items: flex-start;
}
.submit-card {
  margin-top: 16px;
}
.feedback-card {
  margin-top: 16px;
}
.fb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.fb-head h3 {
  margin: 0;
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
.submit-card h3 {
  margin: 0 0 12px;
}
.upload-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 12px 0;
}
.file-tip {
  font-size: 13px;
  color: #6b7280;
}
.actions {
  text-align: right;
}
.attach-box {
  margin-top: 16px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 6px;
}
.attach-label {
  color: #6b7280;
  font-size: 13px;
  margin-bottom: 6px;
}
.attach-link {
  margin: 4px 0;
}
</style>
