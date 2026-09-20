<template>
  <div class="schools-page">
    <!-- 概览 -->
    <div class="stat-cards">
      <div class="stat-card">
        <div class="stat-num">{{ overview.school_count ?? '-' }}</div>
        <div class="stat-label">学校总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ overview.active_school_count ?? '-' }}</div>
        <div class="stat-label">启用中</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ overview.student_count ?? '-' }}</div>
        <div class="stat-label">学生总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ overview.teacher_count ?? '-' }}</div>
        <div class="stat-label">教师总数</div>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">开通学校</el-button>
    </div>

    <!-- 列表 -->
    <StateView
      :loading="loading"
      :error="error"
      :empty="!items.length"
      :columns="8"
      empty-description="暂无学校"
      @retry="load"
    >
      <el-table :data="items" v-loading="loading" border>
        <el-table-column prop="name" label="学校名称" min-width="180" />
        <el-table-column prop="code" label="代码" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="class_count" label="班级" width="80" align="center" />
        <el-table-column prop="student_count" label="学生" width="80" align="center" />
        <el-table-column prop="teacher_count" label="教师" width="80" align="center" />
        <el-table-column prop="phone" label="电话" min-width="140" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              :type="row.status === 'active' ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 'active' ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="removeSchool(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </StateView>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑学校' : '开通学校'" width="520px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="学校名称" required>
          <el-input v-model="form.name" placeholder="如：XX 职业技术学校" />
        </el-form-item>
        <el-form-item label="学校代码" required>
          <el-input v-model="form.code" placeholder="如：XYZJ01" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.address" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <template v-if="!isEdit">
          <el-divider content-position="left">首位学校管理员（可选）</el-divider>
          <el-form-item label="管理员账号">
            <el-input v-model="form.admin_username" placeholder="如：admin02" />
          </el-form-item>
          <el-form-item label="管理员姓名">
            <el-input v-model="form.admin_name" />
          </el-form-item>
          <el-form-item label="初始密码">
            <el-input v-model="form.admin_password" placeholder="默认 School@123" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveSchool">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import StateView from '../../components/StateView.vue'
import { useCrudList } from '../../composables/useCrudList'
import { schoolApi, adminApi } from '../../api'

const saving = ref(false)
const overview = ref({})
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)

const emptyForm = () => ({
  name: '',
  code: '',
  address: '',
  phone: '',
  admin_username: '',
  admin_name: '',
  admin_password: '',
})
const form = reactive(emptyForm())

// 学校全量列表 + 平台概览两路请求合并取回；wrapper 合成 total，保持原行为等价。
const { items, loading, error, load } = useCrudList(async (params) => {
  const rest = { ...params }
  delete rest.page
  delete rest.page_size
  const [s, o] = await Promise.all([schoolApi.list(rest), adminApi.platformOverview()])
  overview.value = o
  return { items: s.items || [], total: (s.items || []).length }
})

function openCreate() {
  isEdit.value = false
  editId.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row) {
  isEdit.value = true
  editId.value = row.id
  Object.assign(form, {
    name: row.name,
    code: row.code,
    address: row.address,
    phone: row.phone,
    admin_username: '',
    admin_name: '',
    admin_password: '',
  })
  dialogVisible.value = true
}

async function saveSchool() {
  if (!form.name || !form.code) return ElMessage.warning('请填写学校名称和代码')
  saving.value = true
  try {
    if (isEdit.value) {
      await schoolApi.update(editId.value, {
        name: form.name,
        address: form.address,
        phone: form.phone,
      })
      ElMessage.success('已保存')
    } else {
      await schoolApi.create(form)
      ElMessage.success('学校已开通')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function toggleStatus(row) {
  const next = row.status === 'active' ? 'disabled' : 'active'
  await schoolApi.setStatus(row.id, next)
  ElMessage.success(next === 'active' ? '已启用' : '已停用')
  load()
}

async function removeSchool(row) {
  await ElMessageBox.confirm(
    `确定删除学校「${row.name}」吗？该校若有班级数据将无法删除。`,
    '删除确认',
    { type: 'warning' }
  )
  await schoolApi.remove(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.stat-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.stat-card {
  background: #fff;
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 20px;
}
.stat-num {
  font-size: 30px;
  font-weight: 600;
  color: var(--el-color-primary);
}
.stat-label {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.toolbar {
  margin-bottom: 16px;
}
</style>
