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
        <el-form-item v-if="isPlatformAdminUser && !editing" label="学校" required>
          <el-select v-model="form.school_id" filterable placeholder="选择学校" style="width: 100%">
            <el-option v-for="s in schools" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
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
import { workLogApi, schoolApi } from '../../api'
import { isPlatformAdmin } from '../../utils/auth'

const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const previewDialog = ref(false)
const previewContent = ref('')
// 平台超管：工作日志无父资源可继承 school_id，创建时须显式选校（非超管不渲染该项、不下发）
const isPlatformAdminUser = isPlatformAdmin()
const schools = ref([])
const form = reactive({ date: '', content: '', school_id: null })

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
  // 本地日期：toISOString() 走 UTC，清晨（UTC 与本地跨天时）会返回差一天的日期
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function openCreate() {
  editing.value = null
  Object.assign(form, { date: today(), content: '', school_id: null })
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
  // 只拷贝表单声明的字段，避免把整行的 id / created_at 等额外键动态注入 reactive
  Object.assign(form, { date: row.date, content: row.content })
  dialog.value = true
}

function preview(row) {
  previewContent.value = row.content
  previewDialog.value = true
}

async function save() {
  // 超管创建必须指定学校（编辑分支不下发、不校验）
  if (isPlatformAdminUser && !editing.value && !form.school_id) {
    return ElMessage.warning('请选择学校')
  }
  saving.value = true
  try {
    // 显式构造载荷：只提交表单声明的字段
    const payload = { date: form.date, content: form.content }
    // 仅超管创建时下发 school_id；教师/校管不下发，后端按其 user.school_id 归属
    if (isPlatformAdminUser && !editing.value) payload.school_id = form.school_id
    if (editing.value) await workLogApi.update(editing.value.id, payload)
    else await workLogApi.create(payload)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}
</script>
