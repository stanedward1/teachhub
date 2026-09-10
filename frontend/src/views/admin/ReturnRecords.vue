<template>
  <div>
    <div class="toolbar">
      <StudentSelect v-model="studentId" v-model:class-id="classId" show-class-filter placeholder="按学生筛选" style="width: 320px" @update:model-value="load" @update:class-id="load" />
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">新增返校记录</el-button>
    </div>

    <div class="page-card">
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column prop="student_name" label="学生" width="130" />
        <el-table-column prop="return_date" label="返校日期" width="130" />
        <el-table-column prop="reason" label="事由" min-width="160" />
        <el-table-column prop="note" label="备注" min-width="160" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <PaginationBar v-model:page="page" v-model:page-size="pageSize" :total="total" @change="load" />
    </div>

    <el-dialog v-model="dialog" title="新增返校记录" width="460px">
      <el-form label-width="80px">
        <el-form-item label="学生" required><StudentSelect v-model="form.student_id" show-class-filter /></el-form-item>
        <el-form-item label="返校日期"><el-date-picker v-model="form.return_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="事由"><el-input v-model="form.reason" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.note" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import StudentSelect from '../../components/StudentSelect.vue'
import SortBar from '../../components/SortBar.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import { useSort } from '../../composables/useSort'
import { returnRecordApi } from '../../api'

const rawItems = ref([])
const { order, useSorted } = useSort('returnrecords')
const items = useSorted(rawItems)
const studentId = ref(null)
const classId = ref(null)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const dialog = ref(false)
const saving = ref(false)
const form = reactive({ student_id: null, return_date: '', reason: '', note: '' })

onMounted(load)

async function load() {
  loading.value = true
  try {
    const res = await returnRecordApi.list({ page: page.value, page_size: pageSize.value, student_id: studentId.value, class_id: classId.value })
    rawItems.value = res.items
    total.value = res.total
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, { student_id: null, return_date: '', reason: '', note: '' })
  dialog.value = true
}

async function save() {
  if (!form.student_id) return ElMessage.warning('请选择学生')
  saving.value = true
  try {
    await returnRecordApi.create(form)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm('确定删除该记录吗？', '提示', { type: 'warning' })
  await returnRecordApi.remove(row.id)
  ElMessage.success('删除成功')
  load()
}
</script>
