<template>
  <div>
    <div class="toolbar">
      <el-select
        v-model="classId"
        placeholder="全部班级"
        clearable
        style="width: 200px"
        @change="load"
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
          <el-table-column label="操作" width="320" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                type="primary"
                @click="$router.push(`/admin/homework/${row.id}/submissions`)"
                >审阅</el-button
              >
              <el-button link type="warning" @click="openUnsubmitted(row)">未交名单</el-button>
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </StateView>
    </div>

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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownEditor from '../../components/MarkdownEditor.vue'
import StateView from '../../components/StateView.vue'
import { homeworkApi, metaApi, uploadFile } from '../../api'

const items = ref([])
const classes = ref([])
const classId = ref(null)
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
  const res = await metaApi.classes()
  classes.value = res.items
  load()
})

async function load() {
  loading.value = true
  error.value = false
  try {
    const res = await homeworkApi.assignments(classId.value ? { class_id: classId.value } : {})
    items.value = res.items
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

function stopRolling() {
  if (rollTimer) {
    clearInterval(rollTimer)
    rollTimer = null
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
  setTimeout(() => {
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
  await ElMessageBox.confirm(`确定删除任务「${row.title}」吗？`, '提示', { type: 'warning' })
  await homeworkApi.deleteAssignment(row.id)
  ElMessage.success('删除成功')
  load()
}

onBeforeUnmount(() => {
  stopRolling()
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
  color: #f56c6c;
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
  color: #909399;
}

.pick-card {
  min-width: 150px;
  padding: 8px 18px;
  border-radius: 8px;
  text-align: center;
  background: #fef0f0;
  border: 1px solid #fbc4c4;
  color: #f56c6c;
}

.pick-card.rolling {
  background: #f4f4f5;
  border-color: #d3d4d6;
  color: #909399;
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
  color: #67c23a;
  font-weight: 600;
}
</style>
