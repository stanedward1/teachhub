<template>
  <div>
    <div class="toolbar">
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">写日志</el-button>
    </div>

    <div class="page-card">
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column prop="date" label="日期" width="130" />
        <el-table-column label="内容预览" min-width="300">
          <template #default="{ row }">{{ (row.content || '').replace(/[#*`]/g, '').slice(0, 80) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="preview(row)">查看</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <PaginationBar v-model:page="page" v-model:page-size="pageSize" :total="total" @change="load" />
    </div>

    <el-dialog v-model="dialog" :title="editing ? '编辑日志' : '写日志'" width="760px">
      <el-form label-width="60px">
        <el-form-item label="日期">
          <el-date-picker v-model="form.date" type="date" value-format="YYYY-MM-DD" style="width: 200px" />
        </el-form-item>
        <el-form-item label="内容">
          <MarkdownEditor v-model="form.content" :rows="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="previewDialog" title="日志详情" width="720px">
      <Markdown :content="previewContent" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Markdown from '../../components/Markdown.vue'
import MarkdownEditor from '../../components/MarkdownEditor.vue'
import SortBar from '../../components/SortBar.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import { useSort } from '../../composables/useSort'
import { workLogApi } from '../../api'

const rawItems = ref([])
const { order, useSorted } = useSort('worklogs')
const items = useSorted(rawItems)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const previewDialog = ref(false)
const previewContent = ref('')
const form = reactive({ date: '', content: '' })

onMounted(load)

async function load() {
  loading.value = true
  try {
    const res = await workLogApi.list({ page: page.value, page_size: pageSize.value })
    rawItems.value = res.items
    total.value = res.total
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function today() {
  return new Date().toISOString().slice(0, 10)
}

function openCreate() {
  editing.value = null
  Object.assign(form, { date: today(), content: '' })
  dialog.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, row)
  dialog.value = true
}

function preview(row) {
  previewContent.value = row.content
  previewDialog.value = true
}

async function save() {
  saving.value = true
  try {
    if (editing.value) await workLogApi.update(editing.value.id, form)
    else await workLogApi.create(form)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm('确定删除该日志吗？', '提示', { type: 'warning' })
  await workLogApi.remove(row.id)
  ElMessage.success('删除成功')
  load()
}
</script>
