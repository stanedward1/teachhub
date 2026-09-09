<template>
  <div>
    <div class="toolbar">
      <el-select v-model="ptype" placeholder="全部类型" clearable style="width: 140px" @change="load">
        <el-option label="积极" value="积极" />
        <el-option label="消极" value="消极" />
      </el-select>
      <StudentSelect v-model="studentId" v-model:classId="classId" showClassFilter placeholder="按学生筛选" style="width: 320px" @update:model-value="load" @update:classId="load" />
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">新增表现记录</el-button>
    </div>

    <div class="page-card">
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column prop="student_name" label="学生" width="130" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row.ptype === '积极' ? 'success' : 'danger'" size="small">{{ row.ptype }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="分值" width="70" align="center">
          <template #default="{ row }">
            <span :style="{ color: (row.points || 0) > 0 ? '#67c23a' : (row.points || 0) < 0 ? '#f56c6c' : '#909399', fontWeight: 600 }">
              {{ (row.points || 0) > 0 ? '+' + (row.points || 0) : (row.points || 0) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="260" />
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        style="margin-top: 16px; justify-content: flex-end"
        layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" :current-page="page"
        @current-change="onPage"
      />
    </div>

    <el-dialog v-model="dialog" title="新增表现记录" width="460px">
      <el-form label-width="80px">
        <el-form-item label="学生" required><StudentSelect v-model="form.student_id" showClassFilter /></el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.ptype" @change="onPtypeChange">
            <el-radio value="积极">积极（加分）</el-radio>
            <el-radio value="消极">消极（减分）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="积分">
          <el-input-number v-model="form.points" :min="-100" :max="100" />
          <span style="margin-left: 8px; color: #909399; font-size: 12px">正数加分，负数减分</span>
        </el-form-item>
        <el-form-item label="内容"><el-input v-model="form.content" type="textarea" :rows="3" /></el-form-item>
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
import { useSort } from '../../composables/useSort'
import { performanceApi } from '../../api'

const rawItems = ref([])
const { order, useSorted } = useSort('performances')
const items = useSorted(rawItems)
const ptype = ref('')
const studentId = ref(null)
const classId = ref(null)
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)
const dialog = ref(false)
const saving = ref(false)
const form = reactive({ student_id: null, ptype: '积极', content: '', points: 1 })

function onPtypeChange(val) {
  // 切换类型时自动调整积分正负
  form.points = val === '积极' ? Math.abs(form.points) : -Math.abs(form.points)
}

onMounted(load)

async function load() {
  loading.value = true
  try {
    const res = await performanceApi.list({ page: page.value, page_size: pageSize, ptype: ptype.value, student_id: studentId.value, class_id: classId.value })
    rawItems.value = res.items
    total.value = res.total
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function onPage(p) {
  page.value = p
  load()
}

function openCreate() {
  Object.assign(form, { student_id: null, ptype: '积极', content: '', points: 1 })
  dialog.value = true
}

async function save() {
  if (!form.student_id) return ElMessage.warning('请选择学生')
  saving.value = true
  try {
    await performanceApi.create(form)
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
  await performanceApi.remove(row.id)
  ElMessage.success('删除成功')
  load()
}
</script>
