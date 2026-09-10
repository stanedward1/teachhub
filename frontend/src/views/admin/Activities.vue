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
        <el-table-column label="配图" width="90" align="center">
          <template #default="{ row }">
            <el-image
              v-if="row.filepath && row.filepath.length"
              :src="'/uploads/' + row.filepath[0]"
              :preview-src-list="row.filepath.map(p => '/uploads/' + p)"
              preview-teleported
              fit="cover"
              style="width: 48px; height: 48px; border-radius: 6px"
            />
            <span v-else style="color: #c0c4cc">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <PaginationBar v-model:page="page" v-model:page-size="pageSize" :total="total" @change="load" />
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
        <el-form-item label="配图">
          <el-upload
            :show-file-list="false"
            :http-request="doUpload"
            accept="image/*"
            multiple
          >
            <el-button>选择图片</el-button>
          </el-upload>
          <div class="preview-list">
            <div v-for="(p, i) in form.filepath" :key="p" class="preview-item">
              <el-image
                :src="'/uploads/' + p"
                :preview-src-list="form.filepath.map(x => '/uploads/' + x)"
                :initial-index="i"
                preview-teleported
                fit="cover"
                style="width: 120px; height: 80px; border-radius: 6px"
              />
              <el-button link type="danger" @click="removeImage(i)">移除</el-button>
            </div>
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
import SortBar from '../../components/SortBar.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import { useSort } from '../../composables/useSort'
import { activityApi, studentApi, uploadFile } from '../../api'

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
const form = reactive({ title: '', class_id: null, content: '', filepath: [] })

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
  Object.assign(form, { title: '', class_id: null, content: '', filepath: [] })
  dialog.value = true
}

async function doUpload({ file }) {
  const res = await uploadFile(file)
  form.filepath.push(res.filepath)
}

function removeImage(i) {
  form.filepath.splice(i, 1)
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

<style scoped>
.preview-list {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.preview-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
</style>
