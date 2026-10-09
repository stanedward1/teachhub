<template>
  <div>
    <el-tabs v-model="tab" @tab-change="reload">
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
        <el-form-item v-if="isPlatformAdminUser && !editing" label="学校" required>
          <el-select v-model="form.school_id" filterable placeholder="选择学校" style="width: 100%">
            <el-option v-for="s in schools" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
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
import { useCrudList } from '../../composables/useCrudList'
import { planApi, schoolApi } from '../../api'
import { isPlatformAdmin } from '../../utils/auth'

const tab = ref('class')
const planType = ref('')
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const previewDialog = ref(false)
const previewContent = ref('')
// 平台超管：计划无父资源可继承 school_id，创建时须显式选校（非超管不渲染该项、不下发）
const isPlatformAdminUser = isPlatformAdmin()
const schools = ref([])
const form = reactive({ title: '', plan_type: '计划', content: '', school_id: null })

// 班级/教师计划总结共用一套列表：按 tab 切换两个接口；无分页，wrapper 合成 total。
// 客户端排序仍由 useSort 处理（items 取 useCrudList 返回的原始列表）。
const {
  items: rawItems,
  loading,
  error,
  load,
  reload,
} = useCrudList(
  async (params) => {
    const rest = { ...params }
    delete rest.page
    delete rest.page_size
    const res =
      tab.value === 'class' ? await planApi.classPlans(rest) : await planApi.teacherPlans(rest)
    return { items: res.items, total: res.items.length }
  },
  {
    buildParams: () => ({ plan_type: planType.value }),
  }
)

const { order, useSorted } = useSort('plans')
const items = useSorted(rawItems)

onMounted(load)

function openCreate() {
  editing.value = null
  Object.assign(form, {
    title: '',
    plan_type: planType.value || '计划',
    content: '',
    school_id: null,
  })
  if (isPlatformAdminUser) loadSchools()
  dialog.value = true
}

// 超管创建时拉取学校列表；返回结构为 { items: [...], total }（见 students_service.list_schools）
async function loadSchools() {
  try {
    const res = await schoolApi.list()
    schools.value = res.items || []
  } catch (e) {
    // 加载失败：下拉为空，提交时会被「请选择学校」拦截；错误提示由全局拦截器统一处理
  }
}

function openEdit(row) {
  editing.value = row
  // 只拷贝表单声明的字段，避免整行的 id 等额外键被动态注入 reactive
  Object.assign(form, { title: row.title, plan_type: row.plan_type, content: row.content })
  dialog.value = true
}

function preview(row) {
  previewContent.value = row.content
  previewDialog.value = true
}

async function save() {
  if (!form.title) return ElMessage.warning('请填写标题')
  // 超管创建必须指定学校（编辑分支不下发、不校验）
  if (isPlatformAdminUser && !editing.value && !form.school_id) {
    return ElMessage.warning('请选择学校')
  }
  saving.value = true
  try {
    // 显式构造载荷：只提交表单声明的字段
    const payload = { title: form.title, plan_type: form.plan_type, content: form.content }
    // 仅超管创建时下发 school_id；教师/校管不下发，后端按其 user.school_id 归属
    if (isPlatformAdminUser && !editing.value) payload.school_id = form.school_id
    const isClass = tab.value === 'class'
    if (editing.value) {
      isClass
        ? await planApi.updateClassPlan(editing.value.id, payload)
        : await planApi.updateTeacherPlan(editing.value.id, payload)
    } else {
      isClass ? await planApi.createClassPlan(payload) : await planApi.createTeacherPlan(payload)
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
  try {
    await ElMessageBox.confirm('确定删除吗？', '提示', { type: 'warning' })
  } catch {
    return // 用户取消确认框：静默返回，不弹任何提示
  }
  tab.value === 'class'
    ? await planApi.removeClassPlan(row.id)
    : await planApi.removeTeacherPlan(row.id)
  ElMessage.success('删除成功')
  load()
}
</script>
