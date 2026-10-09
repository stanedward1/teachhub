<template>
  <div>
    <div class="toolbar">
      <el-select
        v-model="classId"
        placeholder="全部班级"
        clearable
        style="width: 200px"
        @change="onFilterChange"
      >
        <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">新建任务</el-button>
    </div>

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="5"
        empty-description="暂无作业"
        @retry="load"
      >
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="title" label="任务标题" min-width="180" />
          <el-table-column prop="class_name" label="下发班级" width="150" />
          <el-table-column prop="deadline" label="截止时间" width="170" />
          <el-table-column prop="submission_count" label="提交数" width="90" />
          <el-table-column label="操作" width="400" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                @click="$router.push(`/admin/homework/${row.id}/submissions`)"
                >审阅</el-button
              >
              <el-button link type="primary" :loading="aiGradingId === row.id" @click="aiGrade(row)"
                >AI 批改</el-button
              >
              <el-button link type="warning" @click="openUnsubmitted(row)">未交名单</el-button>
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </StateView>
    </div>

    <!-- 任务列表分页：后端按 page/page_size 切页（P1-3），筛选班级变化时回到第 1 页 -->
    <PaginationBar v-model:page="page" v-model:page-size="pageSize" :total="total" @change="load" />

    <el-dialog v-model="dialog" :title="editing ? '编辑任务' : '新建任务'" width="760px">
      <el-form label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="下发班级" required>
          <el-select v-model="form.class_id" style="width: 100%">
            <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker
            v-model="form.deadline"
            type="datetime"
            placeholder="选择截止时间"
            style="width: 100%"
            value-format="YYYY-MM-DD HH:mm"
          />
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="内容" required>
          <MarkdownEditor v-model="form.content" :rows="8" />
        </el-form-item>
        <el-form-item label="附件">
          <div style="width: 100%">
            <el-upload :show-file-list="false" :http-request="doUpload" multiple>
              <el-button>上传附件</el-button>
            </el-upload>
            <div v-for="(att, i) in form.attachments" :key="i" class="attach-item">
              <el-link type="primary" :href="'/uploads/' + att.filepath" target="_blank">{{
                att.filename
              }}</el-link>
              <el-button link type="danger" @click="removeAttachment(i)">移除</el-button>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 未交名单：展示该作业下发班级中尚未提交的学生 -->
    <el-dialog
      v-model="unsubmittedDialog"
      :title="
        unsubmitted && unsubmitted.assignment_title
          ? '未交名单 - ' + unsubmitted.assignment_title
          : '未交名单'
      "
      width="560px"
    >
      <div v-loading="unsubmittedLoading" style="min-height: 80px">
        <template v-if="unsubmitted">
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="应交人数">{{ unsubmitted.total }}</el-descriptions-item>
            <el-descriptions-item label="已交人数">{{
              unsubmitted.submitted_count
            }}</el-descriptions-item>
            <el-descriptions-item label="未交人数">
              <span :class="unsubmitted.unsubmitted_count ? 'danger-text' : 'ok-text'">
                {{ unsubmitted.unsubmitted_count }}
              </span>
            </el-descriptions-item>
          </el-descriptions>

          <!-- 随机点人：在未交学生中等概率抽取，点完一轮自动重置，避免重复点同一个人 -->
          <div v-if="unsubmitted.items.length" class="pick-area">
            <el-button type="primary" plain size="small" :disabled="picking" @click="randomPick">
              {{ picking ? '点名中…' : '随机点人' }}
            </el-button>
            <span class="pick-progress">
              已点 {{ pickedIds.length }} / {{ unsubmitted.items.length }}
            </span>
            <div v-if="picking || picked" class="pick-card" :class="{ rolling: picking }">
              <template v-if="picking">
                <div class="pick-name">{{ rollingName }}</div>
              </template>
              <template v-else>
                <div class="pick-name">{{ picked.name }}</div>
                <div v-if="picked.student_no" class="pick-no">{{ picked.student_no }}</div>
              </template>
            </div>
          </div>

          <div v-if="unsubmitted.items.length" class="unsubmitted-list">
            <el-tag
              v-for="s in unsubmitted.items"
              :key="s.id"
              type="danger"
              :effect="picked && s.id === picked.id ? 'dark' : 'plain'"
            >
              {{ s.name }}
              <span v-if="s.student_no" class="tag-no">{{ s.student_no }}</span>
            </el-tag>
          </div>
          <el-empty v-else description="全员已交，无人缺交" :image-size="60" />
        </template>
      </div>
      <template #footer>
        <el-button @click="unsubmittedDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- AI 批改进度：触发批量批改后弹出，每 2 秒轮询到无在跑任务（finished）为止 -->
    <el-dialog
      v-model="progressDialog"
      :title="progressRow ? 'AI 批改进度 - ' + progressRow.title : 'AI 批改进度'"
      width="520px"
      @close="stopProgressPolling"
    >
      <div v-if="!progress" v-loading="true" style="min-height: 90px"></div>
      <el-empty v-else-if="progress.total === 0" description="该任务暂无提交" :image-size="60" />
      <template v-else>
        <el-progress
          :percentage="progressPercent"
          :status="progress.finished ? 'success' : ''"
          :stroke-width="16"
        />
        <p class="progress-detail">
          已批改 {{ progress.done }} / {{ progress.total }}（成功 {{ progress.success }}，失败
          {{ progress.failed }}，进行中 {{ progress.pending }}，未批改 {{ progress.ungraded }}）
        </p>
        <p v-if="progress.finished" class="progress-done">批改已结束</p>
        <p v-else class="progress-running">AI 正在后台批改，可关闭本窗口，不影响批改进度</p>
        <p v-if="progressFailed" class="progress-retry">进度获取失败，正在重试</p>
      </template>
      <template #footer>
        <el-button type="primary" @click="progressDialog = false">后台运行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownEditor from '../../components/MarkdownEditor.vue'
import StateView from '../../components/StateView.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import { homeworkApi, studentApi, uploadFile } from '../../api'

const items = ref([])
const classes = ref([])
const classId = ref(null)
// 列表分页状态（P1-3）：翻页 / 改每页条数由 PaginationBar 触发 load
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const error = ref(false)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = reactive({
  title: '',
  description: '',
  content: '',
  deadline: null,
  class_id: null,
  short_name: '',
  attachments: [],
})

onMounted(async () => {
  // 用**已鉴权**的班级列表（GET /api/classrooms，依赖 require_teacher）替代公共端点
  // /api/meta/classes：后者无需登录即可访问，未传 school_id 时曾返回**全部学校**的班级；
  // 收紧后未传即返回空。本页需要的正是「当前登录上下文可见的班级」（管理员=本校全部，
  // 教师=自己负责的）。graduated=false 与旧端点「仅未毕业班级」的口径保持一致。
  // 包 try/catch：班级列表拉取失败不应阻断下方 load()（与登录页 loadClasses 同范式）。
  try {
    const res = await studentApi.classrooms({ graduated: 'false' })
    classes.value = res.items
  } catch (e) {
    console.error('[Assignments] 加载班级列表失败:', e)
  }
  load()
})

// AI 批改：纯手动触发（学生提交不会自动批改），只批该作业下尚未批改的提交
const aiGradingId = ref(null)
// 删除任务的重入锁：防止双击重复删除（进入即置位、finally 复位）
const removing = ref(false)

// ---- AI 批改进度：弹窗 + 轮询到「无在跑任务」为止 ----
const progressDialog = ref(false)
const progressRow = ref(null) // 正在查看进度的作业（用于标题）
const progress = ref(null) // 后端进度对象，null 表示尚未拿到首帧
const progressFailed = ref(false) // 本轮轮询是否失败（弹窗内提示用）
let progressTimer = null // 轮询定时器（关闭弹窗 / 卸载时必须清理）
let progressId = null // 当前轮询的作业 id

// 进度条百分比：分子用 done（成功+失败），分母用 total。
// 额度截断时 done/total 可能永远 <100%，此时仍是普通态，仅在 finished 时置成功态。
const progressPercent = computed(() => {
  const p = progress.value
  if (!p || !p.total) return 0
  return Math.round((p.done / p.total) * 100)
})

function stopProgressPolling() {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
  progressId = null
}

// 拉取一次进度；失败只静默跳过本轮（不弹错误 toast），下一轮继续
async function fetchProgress() {
  if (progressId == null) return
  try {
    const res = await homeworkApi.aiGradeProgress(progressId)
    progress.value = res
    progressFailed.value = false
    // pending==0 表示没有在跑的任务了 —— 立即停止轮询（额度截断时也适用）
    if (res.finished) stopProgressPolling()
  } catch (e) {
    progressFailed.value = true
    console.error('获取 AI 批改进度失败', e)
  }
}

function openProgress(row) {
  stopProgressPolling()
  progressRow.value = row
  progress.value = null
  progressFailed.value = false
  progressId = row.id
  progressDialog.value = true
  fetchProgress()
  progressTimer = setInterval(fetchProgress, 2000)
}

async function aiGrade(row) {
  if (!row.submission_count) return ElMessage.warning('该任务暂无提交')
  try {
    await ElMessageBox.confirm(
      `将对「${row.title}」下尚未批改的提交发起 AI 批改（已批改的会自动跳过），确认继续？`,
      'AI 批改',
      { type: 'info' }
    )
  } catch {
    return // 用户取消确认框：静默返回，不弹任何提示
  }
  aiGradingId.value = row.id
  try {
    const res = await homeworkApi.aiGradeAssignment(row.id)
    const parts = [`已发起 ${res.queued} 份 AI 批改`]
    if (res.already_graded) parts.push(`跳过 ${res.already_graded} 份已批改`)
    if (res.skipped && res.skipped > res.already_graded) parts.push(`额度不足跳过其余`)
    ElMessage.success(parts.join('，'))
    // 有实际投递才开进度弹窗；无投递（全部已批改等）维持原提示即可
    if (res.queued > 0) openProgress(row)
  } catch (e) {
    // 失败原因（总开关未开启 / 未配凭证 / 额度耗尽）由全局拦截器提示
  } finally {
    aiGradingId.value = null
  }
}

// 筛选班级变化：结果集变小，必须回到第 1 页再查（否则新条件配旧页码可能越界空页）
function onFilterChange() {
  page.value = 1
  load()
}

async function load() {
  loading.value = true
  error.value = false
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (classId.value) params.class_id = classId.value
    const res = await homeworkApi.assignments(params)
    items.value = res.items
    total.value = res.total
  } catch (e) {
    error.value = true
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    title: '',
    description: '',
    content: '',
    deadline: null,
    class_id: classId.value,
    short_name: '',
    attachments: [],
  })
  dialog.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, {
    title: row.title,
    description: row.description,
    content: row.content,
    deadline: row.deadline,
    class_id: row.class_id,
    short_name: row.short_name,
    attachments: (row.attachments || []).map((a) => ({
      filename: a.filename,
      filepath: a.filepath,
    })),
  })
  dialog.value = true
}

async function doUpload({ file }) {
  const res = await uploadFile(file)
  form.attachments.push({ filename: res.filename, filepath: res.filepath })
  ElMessage.success('附件上传成功')
}

function removeAttachment(i) {
  form.attachments.splice(i, 1)
}

async function save() {
  if (!form.title || !form.content) return ElMessage.warning('请填写标题和内容')
  if (!form.class_id) return ElMessage.warning('请选择下发班级')
  saving.value = true
  try {
    if (editing.value) {
      await homeworkApi.updateAssignment(editing.value.id, form)
    } else {
      await homeworkApi.createAssignment(form)
    }
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

// 未交名单弹框
const unsubmittedDialog = ref(false)
const unsubmittedLoading = ref(false)
const unsubmitted = ref(null)

// 随机点人：picking=滚动中，picked=已定格的学生，pickedIds=本轮已点过的人
const picking = ref(false)
const picked = ref(null)
const rollingName = ref('')
const pickedIds = ref([])
let rollTimer = null
// 定格定时器（setTimeout）的 id：与 rollTimer 一样必须在卸载/重抽前清理，
// 否则弹窗关闭或组件卸载后它仍会触发并写 picking/picked
let rollStopTimer = null

function stopRolling() {
  if (rollTimer) {
    clearInterval(rollTimer)
    rollTimer = null
  }
  if (rollStopTimer) {
    clearTimeout(rollStopTimer)
    rollStopTimer = null
  }
}

function randomPick() {
  const all = (unsubmitted.value && unsubmitted.value.items) || []
  if (!all.length || picking.value) return
  // 从未点过的人里抽；一轮点完自动重置，避免连续点到同一个人
  let pool = all.filter((s) => !pickedIds.value.includes(s.id))
  if (!pool.length) {
    pickedIds.value = []
    pool = all
    ElMessage.info('本轮已全部点过，重新开始一轮')
  }
  const target = pool[Math.floor(Math.random() * pool.length)]
  pickedIds.value = [...pickedIds.value, target.id]

  stopRolling()
  picked.value = null
  picking.value = true
  let i = 0
  rollTimer = setInterval(() => {
    rollingName.value = all[i % all.length].name
    i += 1
  }, 60)
  // 1.2 秒后定格，营造抽签感
  rollStopTimer = setTimeout(() => {
    stopRolling()
    picking.value = false
    picked.value = target
  }, 1200)
}

async function openUnsubmitted(row) {
  stopRolling()
  picking.value = false
  picked.value = null
  pickedIds.value = []
  unsubmittedDialog.value = true
  unsubmitted.value = null
  unsubmittedLoading.value = true
  try {
    unsubmitted.value = await homeworkApi.unsubmitted(row.id)
  } catch (e) {
    // 请求失败（无权限/任务不存在）由全局拦截器提示，此处直接关闭弹框
    unsubmittedDialog.value = false
  } finally {
    unsubmittedLoading.value = false
  }
}

async function remove(row) {
  if (removing.value) return // 防双击：删除在途时忽略重复触发
  removing.value = true
  try {
    try {
      await ElMessageBox.confirm(`确定删除任务「${row.title}」吗？`, '提示', { type: 'warning' })
    } catch {
      return // 用户取消确认框：静默返回，不弹任何提示
    }
    await homeworkApi.deleteAssignment(row.id)
    ElMessage.success('删除成功')
    load()
  } finally {
    removing.value = false
  }
}

onBeforeUnmount(() => {
  stopRolling()
  stopProgressPolling()
})
</script>

<style scoped>
.attach-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.unsubmitted-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.unsubmitted-list .tag-no {
  margin-left: 6px;
  opacity: 0.65;
  font-size: 12px;
}

.danger-text {
  color: var(--el-color-danger);
  font-weight: 600;
}

.pick-area {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 16px;
}

.pick-progress {
  font-size: 12px;
  color: var(--el-color-info);
}

.pick-card {
  min-width: 150px;
  padding: 8px 18px;
  border-radius: 8px;
  text-align: center;
  background: #fef0f0;
  border: 1px solid #fbc4c4;
  color: var(--el-color-danger);
}

.pick-card.rolling {
  background: #f4f4f5;
  border-color: #d3d4d6;
  color: var(--el-color-info);
}

.pick-card .pick-name {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.4;
}

.pick-card .pick-no {
  font-size: 12px;
  opacity: 0.7;
}

.ok-text {
  color: var(--el-color-success);
  font-weight: 600;
}

.progress-detail {
  margin: 14px 0 0;
  font-size: 13px;
  color: #606266;
}

.progress-running {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--el-color-info);
}

.progress-done {
  margin: 8px 0 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-color-success);
}

.progress-retry {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--el-color-warning);
}
</style>
