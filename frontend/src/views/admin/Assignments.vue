<template>
  <div>
    <div class="toolbar">
      <el-select v-model="classId" placeholder="全部班级" clearable style="width: 200px" @change="load">
        <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">新建任务</el-button>
    </div>

    <div class="page-card">
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column prop="title" label="任务标题" min-width="180" />
        <el-table-column prop="class_name" label="下发班级" width="150" />
        <el-table-column prop="deadline" label="截止时间" width="170" />
        <el-table-column prop="submission_count" label="提交数" width="90" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/admin/homework/${row.id}/submissions`)">审阅</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialog" :title="editing ? '编辑任务' : '新建任务'" width="760px">
      <el-form label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="下发班级" required>
          <el-select v-model="form.class_id" style="width: 100%">
            <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止时间">
          <el-date-picker v-model="form.deadline" type="datetime" placeholder="选择截止时间" style="width: 100%" value-format="YYYY-MM-DD HH:mm" />
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="内容" required>
          <MarkdownEditor v-model="form.content" :rows="8" />
        </el-form-item>
        <el-form-item label="附件">
          <div style="width: 100%">
            <el-upload :show-file-list="false" :http-request="doUpload" multiple>
              <el-button>上传附件</el-button>
            </el-upload>
            <div v-for="(att, i) in form.attachments" :key="i" class="attach-item">
              <el-link type="primary" :href="'/uploads/' + att.filepath" target="_blank">{{ att.filename }}</el-link>
              <el-button link type="danger" @click="removeAttachment(i)">移除</el-button>
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
import MarkdownEditor from '../../components/MarkdownEditor.vue'
import { homeworkApi, metaApi, uploadFile } from '../../api'

const items = ref([])
const classes = ref([])
const classId = ref(null)
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = reactive({ title: '', description: '', content: '', deadline: null, class_id: null, short_name: '', attachments: [] })

onMounted(async () => {
  const res = await metaApi.classes()
  classes.value = res.items
  load()
})

async function load() {
  loading.value = true
  try {
    const res = await homeworkApi.assignments(classId.value ? { class_id: classId.value } : {})
    items.value = res.items
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { title: '', description: '', content: '', deadline: null, class_id: classId.value, short_name: '', attachments: [] })
  dialog.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, {
    title: row.title,
    description: row.description,
    content: row.content,
    deadline: row.deadline,
    class_id: row.class_id,
    short_name: row.short_name,
    attachments: (row.attachments || []).map(a => ({ filename: a.filename, filepath: a.filepath }))
  })
  dialog.value = true
}

async function doUpload({ file }) {
  const res = await uploadFile(file)
  form.attachments.push({ filename: res.filename, filepath: res.filepath })
  ElMessage.success('附件上传成功')
}

function removeAttachment(i) {
  form.attachments.splice(i, 1)
}

async function save() {
  if (!form.title || !form.content) return ElMessage.warning('请填写标题和内容')
  if (!form.class_id) return ElMessage.warning('请选择下发班级')
  saving.value = true
  try {
    if (editing.value) {
      await homeworkApi.updateAssignment(editing.value.id, form)
    } else {
      await homeworkApi.createAssignment(form)
    }
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除任务「${row.title}」吗？`, '提示', { type: 'warning' })
  await homeworkApi.deleteAssignment(row.id)
  ElMessage.success('删除成功')
  load()
}
</script>

<style scoped>
.attach-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}
</style>
