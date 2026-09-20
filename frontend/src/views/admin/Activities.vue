<template>
  <div>
    <div class="toolbar">
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">新增活动</el-button>
    </div>

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="4"
        empty-description="暂无活动记录"
        @retry="load"
      >
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="title" label="活动标题" min-width="200" />
          <el-table-column label="内容预览" min-width="260">
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

    <el-dialog v-model="dialog" title="新增活动" width="820px">
      <el-form label-width="80px">
        <el-form-item label="标题" required><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="班级">
          <el-select v-model="form.class_id" style="width: 100%">
            <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
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

    <el-dialog v-model="previewDialog" title="活动详情" width="720px">
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
import { activityApi, studentApi } from '../../api'

const classes = ref([])
const dialog = ref(false)
const saving = ref(false)
const previewDialog = ref(false)
const previewContent = ref('')
const form = reactive({ title: '', class_id: null, content: '' })

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
} = useCrudList(activityApi.list, {
  removeApi: activityApi.remove,
  removeTip: () => '确定删除该活动吗？',
})

const { order, useSorted } = useSort('activities')
const items = useSorted(rawItems)

onMounted(async () => {
  const res = await studentApi.classrooms()
  classes.value = res.items
  load()
})

function plainText(md) {
  return (md || '')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '[图片]')
    .replace(/[-#*`>]/g, '')
    .trim()
}

function openCreate() {
  Object.assign(form, { title: '', class_id: null, content: '' })
  dialog.value = true
}

function preview(row) {
  previewContent.value = row.content
  previewDialog.value = true
}

async function save() {
  if (!form.title) return ElMessage.warning('请填写标题')
  saving.value = true
  try {
    await activityApi.create(form)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}
</script>
