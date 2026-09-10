<template>
  <div>
    <div class="toolbar">
      <el-select v-model="classId" placeholder="选择班级" style="width: 200px" @change="load">
        <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <div class="spacer"></div>
      <el-button type="primary" :disabled="!classId" @click="openAdd">添加课程</el-button>
    </div>

    <div class="page-card">
      <div v-if="!classId" class="empty">请先选择班级</div>
      <table v-else class="schedule-table" v-loading="loading">
        <thead>
          <tr>
            <th>节次</th>
            <th v-for="d in days" :key="d">周{{ d }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in 6" :key="p">
            <td class="period">第{{ p }}节</td>
            <td v-for="d in 5" :key="d" class="cell" @click="openEdit(cell(p, d))">
              <template v-if="cell(p, d)">
                <div class="subject">{{ cell(p, d).subject }}</div>
                <div class="teacher">{{ cell(p, d).teacher_name }}</div>
              </template>
              <span v-else class="plus">+</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <el-dialog v-model="dialog" :title="editing ? '编辑课程' : '添加课程'" width="420px">
      <el-form label-width="80px">
        <el-form-item label="星期">
          <el-select v-model="form.day_of_week" style="width: 100%">
            <el-option v-for="d in 5" :key="d" :label="'周' + days[d - 1]" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="节次">
          <el-select v-model="form.period" style="width: 100%">
            <el-option v-for="p in 6" :key="p" :label="'第 ' + p + ' 节'" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="科目"><el-input v-model="form.subject" /></el-form-item>
        <el-form-item label="教师"><el-input v-model="form.teacher_name" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button v-if="editing" type="danger" plain @click="remove">删除</el-button>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { scheduleApi, studentApi } from '../../api'

const days = ['一', '二', '三', '四', '五']
const classes = ref([])
const classId = ref(null)
const items = ref([])
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = reactive({ day_of_week: 1, period: 1, subject: '', teacher_name: '' })

onMounted(async () => {
  // 管理员看全部，教师只看自己负责的班级
  const res = await studentApi.classrooms()
  classes.value = res.items
})

async function load() {
  loading.value = true
  try {
    const res = await scheduleApi.list({ class_id: classId.value })
    items.value = res.items
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function cell(period, day) {
  return items.value.find((s) => s.period === period && s.day_of_week === day)
}

function openAdd() {
  editing.value = null
  Object.assign(form, { day_of_week: 1, period: 1, subject: '', teacher_name: '' })
  dialog.value = true
}

function openEdit(c) {
  if (!c) return openAdd()
  editing.value = c
  Object.assign(form, { day_of_week: c.day_of_week, period: c.period, subject: c.subject, teacher_name: c.teacher_name })
  dialog.value = true
}

async function save() {
  saving.value = true
  try {
    if (editing.value) {
      await scheduleApi.remove(editing.value.id)
    }
    await scheduleApi.create({ ...form, class_id: classId.value })
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function remove() {
  await scheduleApi.remove(editing.value.id)
  ElMessage.success('删除成功')
  dialog.value = false
  load()
}
</script>

<style scoped>
.schedule-table {
  width: 100%;
  border-collapse: collapse;
}
.schedule-table th,
.schedule-table td {
  border: 1px solid #eef1f6;
  text-align: center;
  padding: 8px;
}
.schedule-table th {
  background: #f8fafc;
  color: #6b7280;
  font-weight: 600;
}
.schedule-table .period {
  background: #f8fafc;
  color: #6b7280;
  width: 70px;
  font-size: 13px;
}
.cell {
  cursor: pointer;
  min-height: 56px;
  transition: background 0.2s;
}
.cell:hover {
  background: #eff6ff;
}
.subject {
  font-weight: 600;
  color: #111827;
}
.teacher {
  font-size: 12px;
  color: #6b7280;
}
.plus {
  color: #cbd5e1;
}
.empty {
  text-align: center;
  color: #9ca3af;
  padding: 60px 0;
}
</style>
