<template>
  <div>
    <el-tabs v-model="tab" @tab-change="load">
      <el-tab-pane label="班级计划总结" name="class" />
      <el-tab-pane label="教师计划总结" name="teacher" />
    </el-tabs>

    <div class="toolbar">
      <el-select
        v-model="planType"
        placeholder="全部类型"
        clearable
        style="width: 140px"
        @change="load"
      >
        <el-option label="计划" value="计划" />
        <el-option label="总结" value="总结" />
      </el-select>
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate"
        >新建{{ tab === 'class' ? '班级' : '教师' }}{{ planType || '计划/总结' }}</el-button
      >
    </div>

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="3"
        empty-description="暂无计划"
        @retry="load"
      >
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="title" label="标题" min-width="220" />
          <el-table-column prop="plan_type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag :type="row.plan_type === '计划' ? 'primary' : 'success'" size="small">{{
                row.plan_type
              }}</el-tag>
            </template>
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
    </div>

    <el-dialog v-model="dialog" :title="editing ? '编辑' : '新建'" width="820px">
      <el-form label-width="80px">
        <el-form-item label="标题" required><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.plan_type">
            <el-radio value="计划">计划</el-radio>
            <el-radio value="总结">总结</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="内容"><MarkdownEditor v-model="form.content" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="previewDialog" title="详情" width="680px">
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
import StateView from '../../components/StateView.vue'
import { useSort } from '../../composables/useSort'
import { planApi } from '../../api'

const tab = ref('class')
const planType = ref('')
const rawItems = ref([])
const loading = ref(false)
const error = ref(false)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const previewDialog = ref(false)
const previewContent = ref('')
const { order, useSorted } = useSort('plans')
const items = useSorted(rawItems)
const form = reactive({ title: '', plan_type: '计划', content: '' })

onMounted(load)

async function load() {
  loading.value = true
  error.value = false
  try {
    const params = { plan_type: planType.value }
    const res =
      tab.value === 'class' ? await planApi.classPlans(params) : await planApi.teacherPlans(params)
    rawItems.value = res.items
  } catch (e) {
    error.value = true
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { title: '', plan_type: planType.value || '计划', content: '' })
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
  if (!form.title) return ElMessage.warning('请填写标题')
  saving.value = true
  try {
    const isClass = tab.value === 'class'
    if (editing.value) {
      isClass
        ? await planApi.updateClassPlan(editing.value.id, form)
        : await planApi.updateTeacherPlan(editing.value.id, form)
    } else {
      isClass ? await planApi.createClassPlan(form) : await planApi.createTeacherPlan(form)
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
  await ElMessageBox.confirm('确定删除吗？', '提示', { type: 'warning' })
  tab.value === 'class'
    ? await planApi.removeClassPlan(row.id)
    : await planApi.removeTeacherPlan(row.id)
  ElMessage.success('删除成功')
  load()
}
</script>
