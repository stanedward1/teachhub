<template>
  <div>
    <div class="toolbar">
      <StudentSelect
        v-model="studentId"
        v-model:class-id="classId"
        show-class-filter
        placeholder="按学生筛选"
        style="width: 320px"
        @update:model-value="load"
        @update:class-id="load"
      />
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">新增谈心记录</el-button>
    </div>

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="4"
        empty-description="暂无谈话记录"
        @retry="load"
      >
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column label="学生" width="130">
            <template #default="{ row }">
              <el-link type="primary" :underline="false" @click="openStudentCard(row)">{{
                row.student_name
              }}</el-link>
            </template>
          </el-table-column>
          <el-table-column label="谈心内容" min-width="280">
            <template #default="{ row }">{{ plainText(row.content).slice(0, 80) }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="时间" width="170" />
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="preview(row)">查看</el-button>
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </StateView>
      <PaginationBar
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="total"
        @change="load"
      />
    </div>

    <el-dialog v-model="dialog" title="新增谈心记录" width="820px">
      <el-form label-width="80px">
        <el-form-item label="学生" required
          ><StudentSelect v-model="form.student_id" show-class-filter
        /></el-form-item>
        <el-form-item label="内容"><MarkdownEditor v-model="form.content" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="previewDialog" title="谈心详情" width="720px">
      <Markdown :content="previewContent" />
    </el-dialog>

    <StudentCard v-model:visible="studentCardVisible" :student-id="studentCardId" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Markdown from '../../components/Markdown.vue'
import MarkdownEditor from '../../components/MarkdownEditor.vue'
import StudentSelect from '../../components/StudentSelect.vue'
import SortBar from '../../components/SortBar.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import StudentCard from '../../components/StudentCard.vue'
import StateView from '../../components/StateView.vue'
import { useSort } from '../../composables/useSort'
import { talkApi } from '../../api'

const rawItems = ref([])
const { order, useSorted } = useSort('talks')
const items = useSorted(rawItems)
const studentId = ref(null)
const classId = ref(null)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const error = ref(false)
const dialog = ref(false)
const saving = ref(false)
const previewDialog = ref(false)
const previewContent = ref('')
const form = reactive({ student_id: null, content: '' })

// 跨模块学生卡片
const studentCardVisible = ref(false)
const studentCardId = ref(null)
function openStudentCard(row) {
  if (!row.student_id) return
  studentCardId.value = row.student_id
  studentCardVisible.value = true
}

onMounted(load)

function plainText(md) {
  return (md || '')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '[图片]')
    .replace(/[-#*`>]/g, '')
    .trim()
}

async function load() {
  loading.value = true
  error.value = false
  try {
    const res = await talkApi.list({
      page: page.value,
      page_size: pageSize.value,
      student_id: studentId.value,
      class_id: classId.value,
    })
    rawItems.value = res.items
    total.value = res.total
  } catch (e) {
    error.value = true
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, { student_id: null, content: '' })
  dialog.value = true
}

function preview(row) {
  previewContent.value = row.content
  previewDialog.value = true
}

async function save() {
  if (!form.student_id) return ElMessage.warning('请选择学生')
  saving.value = true
  try {
    await talkApi.create(form)
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
  await talkApi.remove(row.id)
  ElMessage.success('删除成功')
  load()
}
</script>
