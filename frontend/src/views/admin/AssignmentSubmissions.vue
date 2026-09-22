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
        :columns="7"
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
          <el-table-column label="AI 批改" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.ai_grading_status === 'success'" size="small" type="success"
                >已批改</el-tag
              >
              <el-tag v-else-if="row.ai_grading_status === 'pending'" size="small" type="warning"
                >批改中</el-tag
              >
              <span v-else class="muted">未批改</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="row.is_excellent ? 'success' : 'info'" size="small">
                {{ row.is_excellent ? '优秀' : '普通' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="300" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">查看详情</el-button>
              <el-button
                link
                type="primary"
                :loading="aiGradingId === row.id"
                @click="aiGrade(row)"
                >{{ row.ai_grading_status === 'success' ? '重新批改' : 'AI 批改' }}</el-button
              >
              <el-button v-if="!row.is_excellent" link type="success" @click="mark(row)"
                >选为优秀</el-button
              >
              <el-button
                v-else
                link
                type="warning"
                :loading="unmarkingId === row.id"
                @click="unmark(row)"
                >取消优秀</el-button
              >
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
        <el-button :disabled="saving" @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="confirmMark">确定</el-button>
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
import { useCrudList } from '../../composables/useCrudList'
import { homeworkApi } from '../../api'

const route = useRoute()
const router = useRouter()
const assignment = ref(null)
const dialog = ref(false)
const note = ref('')
const target = ref(null)
const saving = ref(false) // 评选优秀提交中（防重复提交）
const unmarkingId = ref(null) // 正在取消优秀的提交 id

// 作业提交审阅：单个作业的「作业详情 + 全部提交」一次取回。非标准分页 CRUD，用 wrapper
// 把两路请求收敛进 useCrudList，去掉手写 loading/error/items 样板（不改后端）。
const { items, loading, error, load } = useCrudList(async (_params) => {
  const [a, s] = await Promise.all([
    homeworkApi.assignment(route.params.id),
    homeworkApi.submissions(route.params.id),
  ])
  assignment.value = a
  return { items: s.items, total: s.items.length }
})

onMounted(load)

function mark(row) {
  target.value = row
  note.value = ''
  dialog.value = true
}

function openDetail(row) {
  router.push(`/admin/homework/${route.params.id}/submissions/${row.id}`)
}

async function confirmMark() {
  // 防重复提交：确定按钮无 loading 时双击会并发两个 POST，第二个请求的「已入选」预检
  // 先于第一个请求的写入生效，最终撞数据库唯一索引报 409「数据冲突」。
  if (saving.value) return
  saving.value = true
  try {
    await homeworkApi.markExcellent(target.value.id, { note: note.value })
    ElMessage.success('已评选为优秀作品')
    dialog.value = false
    load()
  } catch (e) {
    // 失败原因由全局拦截器提示（如「该作品已入选优秀」）
  } finally {
    saving.value = false
  }
}

async function unmark(row) {
  if (unmarkingId.value === row.id) return
  unmarkingId.value = row.id
  try {
    await homeworkApi.unmarkExcellent(row.id)
    ElMessage.success('已取消优秀')
    await load()
  } catch (e) {
    // 失败原因由全局拦截器提示
  } finally {
    unmarkingId.value = null
  }
}

// AI 批改：单份触发（已有结果则重跑覆盖）；未批改 / 失败的提交也可单独补批
const aiGradingId = ref(null)

async function aiGrade(row) {
  aiGradingId.value = row.id
  try {
    await homeworkApi.aiGradeSubmission(row.id)
    ElMessage.success('已发起 AI 批改，稍后刷新查看结果')
    // 批改在后台线程执行，稍作延迟再拉取，避免立刻刷新仍是「批改中」
    setTimeout(load, 1200)
  } catch (e) {
    // 失败原因（总开关未开启 / 未配凭证 / 额度耗尽）由全局拦截器提示
  } finally {
    aiGradingId.value = null
  }
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
.muted {
  color: #9ca3af;
  font-size: 13px;
}
</style>
