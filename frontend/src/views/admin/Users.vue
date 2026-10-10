<template>
  <div>
    <div class="toolbar">
      <el-select
        v-model="role"
        placeholder="全部角色"
        clearable
        style="width: 160px"
        @change="reload"
      >
        <el-option :label="ROLE_LABELS[ROLES.SUPER_ADMIN]" :value="ROLES.SUPER_ADMIN" />
        <el-option :label="ROLE_LABELS[ROLES.SCHOOL_ADMIN]" :value="ROLES.SCHOOL_ADMIN" />
        <el-option :label="ROLE_LABELS[ROLES.TEACHER]" :value="ROLES.TEACHER" />
        <el-option :label="ROLE_LABELS[ROLES.STUDENT]" :value="ROLES.STUDENT" />
      </el-select>
      <el-input
        v-model="keyword"
        placeholder="搜索姓名/用户名"
        clearable
        style="width: 200px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-button @click="reload">查询</el-button>
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">新增账号</el-button>
    </div>

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="7"
        empty-description="暂无用户"
        @retry="load"
      >
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="username" label="用户名" width="140" />
          <el-table-column prop="name" label="姓名" width="120" />
          <el-table-column label="角色" width="100">
            <template #default="{ row }">
              <el-tag :type="roleType(row.role)" size="small">{{ roleText(row.role) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="phone" label="电话" width="140" />
          <el-table-column prop="class_name" label="班级" width="140" />
          <el-table-column label="班级身份" min-width="200">
            <template #default="{ row }">
              <template v-if="row.role === 'teacher'">
                <el-tag
                  v-for="c in row.head_classes || []"
                  :key="'h' + c"
                  size="small"
                  type="warning"
                  style="margin-right: 4px"
                  >班主任·{{ c }}</el-tag
                >
                <el-tag
                  v-for="c in row.subject_classes || []"
                  :key="'s' + c"
                  size="small"
                  type="info"
                  style="margin-right: 4px"
                  >科任·{{ c }}</el-tag
                >
                <span
                  v-if="!(row.head_classes || []).length && !(row.subject_classes || []).length"
                  style="color: #9ca3af"
                  >未分配班级</span
                >
              </template>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button v-if="canResetPwd(row)" link type="warning" @click="resetPwd(row)"
                >重置密码</el-button
              >
              <el-button v-if="canRemove(row)" link type="danger" @click="remove(row)"
                >删除</el-button
              >
            </template>
          </el-table-column>
        </el-table>
      </StateView>
    </div>

    <el-dialog v-model="dialog" :title="editing ? '编辑账号' : '新增账号'" width="460px">
      <el-form label-width="80px">
        <el-form-item label="用户名" required
          ><el-input v-model="form.username" :disabled="!!editing"
        /></el-form-item>
        <el-form-item v-if="!editing" label="密码"
          ><el-input v-model="form.password" placeholder="默认 123456"
        /></el-form-item>
        <el-form-item label="姓名" required
          ><el-input v-model="form.name" :disabled="nameDisabled"
        /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width: 100%" :disabled="roleDisabled">
            <el-option :label="ROLE_LABELS[ROLES.SCHOOL_ADMIN]" :value="ROLES.SCHOOL_ADMIN" />
            <el-option :label="ROLE_LABELS[ROLES.TEACHER]" :value="ROLES.TEACHER" />
            <el-option :label="ROLE_LABELS[ROLES.STUDENT]" :value="ROLES.STUDENT" />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="isPlatformUser && form.role !== 'super_admin'"
          label="所属学校"
          required
        >
          <el-select
            v-model="form.school_id"
            placeholder="请选择学校"
            style="width: 100%"
            :disabled="!!editing"
          >
            <el-option v-for="s in schools" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="电话"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item v-if="form.role === 'student'" label="班级">
          <el-select v-model="form.class_id" clearable style="width: 100%">
            <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
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
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useDebouncedRef } from '../../composables/useDebouncedRef'
import { ElMessage, ElMessageBox } from 'element-plus'
import StateView from '../../components/StateView.vue'
import { useCrudList } from '../../composables/useCrudList'
import { adminApi, studentApi, schoolApi } from '../../api'
import { getUser, isPlatformAdmin } from '../../utils/auth'
import {
  canManageUser,
  roleLabel as roleText,
  roleTagType as roleType,
  ROLE_LABELS,
  ROLES,
} from '../../utils/roles'

const classes = ref([])
const schools = ref([])
const role = ref('')
const keyword = useDebouncedRef('', 300)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
// 表单初始值工厂：reactive 初始化与 openCreate 复用同一份字面量，避免两处漂移
const emptyForm = () => ({
  username: '',
  password: '',
  name: '',
  role: 'teacher',
  phone: '',
  class_id: null,
  school_id: null,
})
const form = reactive(emptyForm())
const { items, loading, error, load, reload, remove } = useCrudList(adminApi.users, {
  removeApi: adminApi.removeUser,
  buildParams: () => ({ role: role.value, keyword: keyword.value }),
  removeTip: (row) => `确定删除账号「${row.name}」吗？`,
})
watch(keyword, reload)

// 当前登录用户角色来源：utils/auth getUser()（localStorage 会话）
const currentUser = getUser()
// 平台超管：可跨校建号，新增/编辑表单需显式指定「所属学校」
const isPlatformUser = isPlatformAdmin()

// 教师不能重置其他教师/管理员的密码
function canResetPwd(row) {
  return canManageUser(currentUser?.role, row.role)
}
// 教师不能删除其他教师/管理员
function canRemove(row) {
  return canManageUser(currentUser?.role, row.role)
}
// 教师编辑其他教师/管理员时禁止修改角色
const roleDisabled = computed(
  () => !!editing.value && !canManageUser(currentUser?.role, editing.value.role)
)
// 教师编辑其他教师/管理员时禁止修改姓名
const nameDisabled = computed(
  () => !!editing.value && !canManageUser(currentUser?.role, editing.value.role)
)

onMounted(async () => {
  // 平台超管需按校建号：预加载学校列表（GET /api/schools 对超管返回全部）
  if (isPlatformUser) {
    try {
      const sres = await schoolApi.list()
      schools.value = sres.items || []
    } catch (e) {
      schools.value = []
    }
  }
  const res = await studentApi.classrooms()
  classes.value = res.items
  load()
})

function openCreate() {
  editing.value = null
  Object.assign(form, emptyForm())
  dialog.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, {
    username: row.username,
    name: row.name,
    role: row.role,
    phone: row.phone,
    class_id: row.class_id,
    school_id: row.school_id ?? null,
  })
  dialog.value = true
}

async function save() {
  if (!form.username || !form.name) return ElMessage.warning('请填写用户名和姓名')
  // 平台超管建号必须指定学校，否则后端会拒绝（跨租户账号防护）
  if (isPlatformUser && form.role !== 'super_admin' && !form.school_id) {
    return ElMessage.warning('请选择账号所属学校')
  }
  saving.value = true
  try {
    const payload = { ...form }
    // 非平台超管不下发 school_id：仍按后端「本校」逻辑回填，避免越权指定他校
    if (!isPlatformUser) delete payload.school_id
    if (editing.value) await adminApi.updateUser(editing.value.id, payload)
    else await adminApi.createUser(payload)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function resetPwd(row) {
  try {
    await ElMessageBox.confirm(`确定将「${row.name}」的密码重置为 123456 吗？`, '提示', {
      type: 'warning',
    })
  } catch {
    return // 用户取消确认框：静默返回，不弹任何提示
  }
  await adminApi.resetPassword(row.id, { password: '123456' })
  ElMessage.success('密码已重置为 123456')
}
</script>
