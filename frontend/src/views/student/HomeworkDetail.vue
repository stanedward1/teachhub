<template>
  <div v-if="assignment">
    <el-page-header content="作业详情" @back="$router.back()" class="mb" />
    <div class="page-card">
      <div class="hd">
        <div>
          <h2 class="page-title">{{ assignment.title }}</h2>
          <p class="page-subtitle">
            {{ assignment.class_name }} · {{ assignment.creator_name }} · 截止 {{ assignment.deadline || '不限' }}
          </p>
        </div>
        <el-tag :type="submitted ? 'success' : 'warning'">{{ submitted ? '已提交' : '待提交' }}</el-tag>
      </div>
      <el-divider />
      <Markdown :content="assignment.content" />
      <div v-if="assignment.attachments && assignment.attachments.length" class="attach-box">
        <span class="attach-label">任务附件：</span>
        <div v-for="(att, i) in assignment.attachments" :key="i" class="attach-link">
          <el-link type="primary" :href="'/uploads/' + att.filepath" target="_blank">{{ att.filename }}</el-link>
        </div>
      </div>
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
import { homeworkApi, uploadFile } from '../../api'

const route = useRoute()
const assignment = ref(null)
const content = ref('')
const submitted = ref(false)
const submitting = ref(false)
const filepath = ref('')
const filename = ref('')

onMounted(async () => {
  await load()
})

async function load() {
  const res = await homeworkApi.assignment(route.params.id)
  assignment.value = res
  const subs = await homeworkApi.submissions(route.params.id)
  if (subs.items.length > 0) {
    submitted.value = true
    content.value = subs.items[0].content || ''
    filepath.value = subs.items[0].filepath || ''
    filename.value = subs.items[0].filename || ''
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
    await homeworkApi.submit(route.params.id, {
      content: content.value,
      filepath: filepath.value,
      filename: filename.value
    })
    ElMessage.success('提交成功')
    submitted.value = true
  } catch (e) {
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
