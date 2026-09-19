<template>
  <div>
    <el-page-header
      :content="assignment?.title || '提交审阅'"
      @back="$router.back()"
      style="margin-bottom: 16px"
    />

    <!-- 任务正文（Markdown 渲染） -->
    <div class="page-card" v-if="assignment?.content">
      <div style="font-weight: 500; margin-bottom: 12px; color: #303133">任务说明</div>
      <Markdown :content="assignment.content" />
    </div>

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="6"
        empty-description="暂无提交记录"
        @retry="load"
      >
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="student_name" label="学生" width="120" />
          <el-table-column label="作业内容" min-width="300">
            <template #default="{ row }">
              <div class="content-preview" v-if="row.content">
                <Markdown :content="row.content" />
              </div>
              <span v-else style="color: #9ca3af">（仅上传附件）</span>
            </template>
          </el-table-column>
          <el-table-column prop="filename" label="附件" width="140">
            <template #default="{ row }">
              <a v-if="row.filepath" :href="'/uploads/' + row.filepath" target="_blank">{{
                row.filename || '下载'
              }}</a>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="提交时间" width="170" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="row.is_excellent ? 'success' : 'info'" size="small">
                {{ row.is_excellent ? '优秀' : '普通' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">查看详情</el-button>
              <el-button v-if="!row.is_excellent" link type="success" @click="mark(row)"
                >选为优秀</el-button
              >
              <el-button v-else link type="warning" @click="unmark(row)">取消优秀</el-button>
            </template>
          </el-table-column>
        </el-table>
      </StateView>
    </div>

    <el-dialog v-model="dialog" title="评选优秀作品" width="480px">
      <el-form label-width="80px">
        <el-form-item label="点评语">
          <el-input v-model="note" type="textarea" :rows="3" placeholder="可选：写下点评语" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="confirmMark">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Markdown from '../../components/Markdown.vue'
import StateView from '../../components/StateView.vue'
import { homeworkApi } from '../../api'

const route = useRoute()
const router = useRouter()
const items = ref([])
const assignment = ref(null)
const loading = ref(true)
const error = ref(false)
const dialog = ref(false)
const note = ref('')
const target = ref(null)

onMounted(load)

async function load() {
  loading.value = true
  error.value = false
  try {
    assignment.value = await homeworkApi.assignment(route.params.id)
    const res = await homeworkApi.submissions(route.params.id)
    items.value = res.items
  } catch (e) {
    error.value = true
  } finally {
    loading.value = false
  }
}

function mark(row) {
  target.value = row
  note.value = ''
  dialog.value = true
}

function openDetail(row) {
  router.push(`/admin/homework/${route.params.id}/submissions/${row.id}`)
}

async function confirmMark() {
  await homeworkApi.markExcellent(target.value.id, { note: note.value })
  ElMessage.success('已评选为优秀作品')
  dialog.value = false
  load()
}

async function unmark(row) {
  await homeworkApi.unmarkExcellent(row.id)
  ElMessage.success('已取消优秀')
  load()
}
</script>

<style scoped>
.content-preview {
  max-height: 120px;
  overflow: hidden;
  position: relative;
  -webkit-line-clamp: 5;
  display: -webkit-box;
  -webkit-box-orient: vertical;
}
.content-preview :deep(.md-body) {
  font-size: 13px;
}
.content-preview :deep(.md-body) h1,
.content-preview :deep(.md-body) h2,
.content-preview :deep(.md-body) h3 {
  font-size: 14px;
  margin: 4px 0;
}
.content-preview :deep(.md-body) p {
  margin: 4px 0;
}
.content-preview :deep(.md-body) pre {
  margin: 4px 0;
  padding: 6px 10px;
  font-size: 12px;
}
.content-preview :deep(.md-body) img {
  max-width: 200px;
  max-height: 150px;
}
.empty {
  text-align: center;
  color: #9ca3af;
  padding: 40px 0;
}
</style>
