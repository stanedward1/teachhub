<template>
  <div>
    <div class="toolbar">
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">写日志</el-button>
    </div>

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="3"
        empty-description="暂无工作日志"
        @retry="load"
      >
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="date" label="日期" width="130" />
          <el-table-column label="内容预览" min-width="300">
            <template #default="{ row }">{{
              (row.content || '').replace(/[#*`]/g, '').slice(0, 80)
            }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="preview(row)">查看</el-button>
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
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

    <el-dialog v-model="dialog" :title="editing ? '编辑日志' : '写日志'" width="820px">
      <el-form label-width="60px">
        <el-form-item label="日期">
          <el-date-picker
            v-model="form.date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="内容">
          <MarkdownEditor v-model="form.content" />
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
import { ElMessage } from 'element-plus'
import Markdown from '../../components/Markdown.vue'
import MarkdownEditor from '../../components/MarkdownEditor.vue'
import SortBar from '../../components/SortBar.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import StateView from '../../components/StateView.vue'
import { useSort } from '../../composables/useSort'
import { useCrudList } from '../../composables/useCrudList'
import { workLogApi } from '../../api'

const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const previewDialog = ref(false)
const previewContent = ref('')
const form = reactive({ date: '', content: '' })

// 列表取数 / 分页 / 删除：统一由 useCrudList 提供，本页只描述差异（删除文案）
const {
  items: rawItems,
  page,
  pageSize,
  total,
  loading,
  error,
  load,
  remove,
} = useCrudList(workLogApi.list, {
  removeApi: workLogApi.remove,
  removeTip: () => '确定删除该日志吗？',
})

const { order, useSorted } = useSort('worklogs')
const items = useSorted(rawItems)

onMounted(load)

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
</script>
