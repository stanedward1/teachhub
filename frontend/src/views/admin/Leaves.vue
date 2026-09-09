<template>
  <div>
    <div class="toolbar">
      <el-select v-model="status" placeholder="全部状态" clearable style="width: 140px" @change="load">
        <el-option label="登记" value="登记" />
        <el-option label="已销假" value="已销假" />
      </el-select>
      <StudentSelect v-model="studentId" v-model:classId="classId" showClassFilter placeholder="按学生筛选" style="width: 320px" @update:model-value="load" @update:classId="load" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">登记请假</el-button>
      <SortBar v-model="order" />
    </div>

    <div class="page-card">
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column label="学生" width="120">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="openStudentCard(row)">{{ row.student_name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="事由" min-width="180" />
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === '已销假' ? 'success' : 'warning'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status !== '已销假'" link type="success" @click="finish(row)">销假</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无请假记录">
            <el-button type="primary" @click="openCreate">登记请假</el-button>
          </el-empty>
        </template>
      </el-table>
      <PaginationBar v-model:page="page" v-model:pageSize="pageSize" :total="total" @change="load" />
    </div>

    <el-dialog v-model="dialog" :title="editing ? '编辑请假' : '登记请假'" width="460px">
      <el-form label-width="80px">
        <el-form-item label="学生" required><StudentSelect v-model="form.student_id" showClassFilter /></el-form-item>
        <el-form-item label="事由"><el-input v-model="form.reason" /></el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <StudentCard v-model:visible="studentCardVisible" :student-id="studentCardId" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import StudentSelect from '../../components/StudentSelect.vue'
import SortBar from '../../components/SortBar.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import StudentCard from '../../components/StudentCard.vue'
import { useSort } from '../../composables/useSort.js'
import { leaveApi } from '../../api'

const rawItems = ref([])
const { order, useSorted } = useSort('leaves')
const items = useSorted(rawItems)
const status = ref('')
const studentId = ref(null)
const classId = ref(null)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = reactive({ student_id: null, reason: '', start_date: '', end_date: '' })

// 跨模块学生卡片
const studentCardVisible = ref(false)
const studentCardId = ref(null)
function openStudentCard(row) {
  if (!row.student_id) return
  studentCardId.value = row.student_id
  studentCardVisible.value = true
}

onMounted(load)

async function load() {
  loading.value = true
  try {
    const res = await leaveApi.list({ page: page.value, page_size: pageSize.value, status: status.value, student_id: studentId.value, class_id: classId.value })
    rawItems.value = res.items
    total.value = res.total
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { student_id: null, reason: '', start_date: '', end_date: '' })
  dialog.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, row)
  dialog.value = true
}

async function save() {
  if (!form.student_id) return ElMessage.warning('请选择学生')
  saving.value = true
  try {
    if (editing.value) await leaveApi.update(editing.value.id, form)
    else await leaveApi.create(form)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function finish(row) {
  await leaveApi.update(row.id, { status: '已销假' })
  ElMessage.success('已销假')
  load()
}

async function remove(row) {
  await ElMessageBox.confirm('确定删除该记录吗？', '提示', { type: 'warning' })
  await leaveApi.remove(row.id)
  ElMessage.success('删除成功')
  load()
}
</script>
