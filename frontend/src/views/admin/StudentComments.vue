<template>
  <div>
    <div class="toolbar">
      <StudentSelect v-model="studentId" v-model:class-id="classId" show-class-filter placeholder="按学生筛选" style="width: 320px" @update:model-value="load" @update:class-id="load" />
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">编写评语</el-button>
    </div>

    <div class="page-card">
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column prop="student_name" label="学生" width="130" />
        <el-table-column prop="content" label="评语内容" min-width="300" />
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <PaginationBar v-model:page="page" v-model:page-size="pageSize" :total="total" @change="load" />
    </div>

    <el-dialog v-model="dialog" :title="editing ? '编辑评语' : '编写评语'" width="500px">
      <el-form label-width="80px">
        <el-form-item label="学生" required><StudentSelect v-model="form.student_id" show-class-filter /></el-form-item>
        <el-form-item label="评语">
          <el-input v-model="form.content" type="textarea" :rows="6" placeholder="可点击下方「AI 生成草稿」自动填充评语..." />
          <div style="margin-top: 8px; display: flex; align-items: center; gap: 8px;">
            <el-button size="small" type="primary" plain :loading="suggesting" :disabled="!form.student_id" @click="suggestComment">
              <el-icon style="margin-right: 4px;"><MagicStick /></el-icon>AI 生成草稿
            </el-button>
            <span style="font-size: 12px; color: #909399;">根据该生成绩、表现、考勤、积分自动生成，可再编辑</span>
          </div>
        </el-form-item>
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
import { studentCommentApi } from '../../api'

const rawItems = ref([])
const { order, useSorted } = useSort('studentcomments')
const items = useSorted(rawItems)
const studentId = ref(null)
const classId = ref(null)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const suggesting = ref(false)
const form = reactive({ student_id: null, content: '' })

onMounted(load)

async function load() {
  loading.value = true
  try {
    const res = await studentCommentApi.list({ page: page.value, page_size: pageSize.value, student_id: studentId.value, class_id: classId.value })
    rawItems.value = res.items
    total.value = res.total
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { student_id: null, content: '' })
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
    if (editing.value) await studentCommentApi.update(editing.value.id, form)
    else await studentCommentApi.create(form)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm('确定删除该评语吗？', '提示', { type: 'warning' })
  await studentCommentApi.remove(row.id)
  ElMessage.success('删除成功')
  load()
}
</script>
