<template>
  <div>
    <div class="toolbar">
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">新增活动</el-button>
    </div>

    <div class="page-card">
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column prop="title" label="活动标题" min-width="220" />
        <el-table-column prop="content" label="内容" min-width="240" />
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <PaginationBar v-model:page="page" v-model:pageSize="pageSize" :total="total" @change="load" />
    </div>

    <el-dialog v-model="dialog" title="新增活动" width="520px">
      <el-form label-width="80px">
        <el-form-item label="标题" required><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="班级">
          <el-select v-model="form.class_id" style="width: 100%">
            <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容"><el-input v-model="form.content" type="textarea" :rows="4" /></el-form-item>
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
import SortBar from '../../components/SortBar.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import { useSort } from '../../composables/useSort'
import { activityApi, metaApi, studentApi } from '../../api'

const rawItems = ref([])
const classes = ref([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const dialog = ref(false)
const saving = ref(false)
const { order, useSorted } = useSort('activities')
const items = useSorted(rawItems)
const form = reactive({ title: '', class_id: null, content: '' })

onMounted(async () => {
  const res = await studentApi.classrooms()
  classes.value = res.items
  load()
})

async function load() {
  loading.value = true
  try {
    const res = await activityApi.list({ page: page.value, page_size: pageSize.value })
    rawItems.value = res.items
    total.value = res.total
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, { title: '', class_id: null, content: '' })
  dialog.value = true
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

async function remove(row) {
  await ElMessageBox.confirm('确定删除该活动吗？', '提示', { type: 'warning' })
  await activityApi.remove(row.id)
  ElMessage.success('删除成功')
  load()
}
</script>
