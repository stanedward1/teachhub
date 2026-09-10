<template>
  <div>
    <div class="toolbar">
      <el-select v-model="graduatedFilter" style="width: 120px" @change="load">
        <el-option label="在读班级" value="false" />
        <el-option label="已毕业" value="true" />
        <el-option label="全部" value="" />
      </el-select>
      <div class="spacer"></div>
      <el-button v-if="isAdmin" type="primary" @click="openCreate">新增班级</el-button>
    </div>
    <div class="page-card">
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="班级名称" min-width="180" />
        <el-table-column prop="code" label="班级代码" width="120" />
        <el-table-column prop="major" label="专业" width="140" />
        <el-table-column prop="grade" label="年级" width="100" />
        <el-table-column label="班级教师" width="120">
          <template #default="{ row }">
            <span>{{ row.teacher_name || '未分配' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="student_count" label="学生数" width="90" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_graduated ? 'info' : 'success'" size="small">
              {{ row.is_graduated ? '已毕业' : '在读' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="isAdmin" link type="success" @click="openTeachers(row)">科任</el-button>
            <el-button v-if="isAdmin" link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialog" :title="editing ? '编辑班级' : '新增班级'" width="480px">
      <el-form label-width="90px">
        <el-form-item label="班级名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="班级代码" required><el-input v-model="form.code" /></el-form-item>
        <el-form-item label="专业"><el-input v-model="form.major" /></el-form-item>
        <el-form-item label="年级">
          <el-select v-model="form.grade" style="width: 100%">
            <el-option v-for="g in ['一年级', '二年级', '三年级', '四年级', '五年级', '六年级']" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <!-- 班级教师：管理员可指定/修改，教师编辑时隐藏 -->
        <el-form-item v-if="isAdmin" label="班级教师">
          <el-select v-model="form.teacher_id" clearable filterable placeholder="选择班主任" style="width: 100%">
            <el-option v-for="t in teachers" :key="t.id" :label="`${t.name}（${t.username}）`" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="毕业状态">
          <el-switch v-model="form.is_graduated" active-text="已毕业" inactive-text="在读" />
          <div v-if="form.is_graduated" style="color: #e6a23c; font-size: 12px; line-height: 1.5; margin-top: 4px;">
            标记毕业后，教师与管理员将无法再对该班所有学生进行各项操作。
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 科任老师管理 -->
    <el-dialog v-model="teacherDialog" :title="`科任老师 - ${currentClass?.name || ''}`" width="480px">
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
        班主任与科任老师均可对该班级的学生、成绩、作业等进行各项操作。
      </el-alert>
      <div class="teacher-list">
        <div v-for="t in classTeacherList" :key="t.teacher_id" class="teacher-item">
          <span class="teacher-name">{{ t.name }}（{{ t.username }}）</span>
          <el-tag v-if="t.is_head" size="small" type="warning">班主任</el-tag>
          <el-tag v-else size="small" type="info">科任</el-tag>
          <el-button v-if="!t.is_head" link type="danger" @click="removeTeacher(t)">移除</el-button>
        </div>
        <div v-if="!classTeacherList.length" class="empty-state">暂无教师</div>
      </div>
      <div class="teacher-add">
        <el-select v-model="newTeacherId" filterable placeholder="选择教师" style="flex: 1">
          <el-option v-for="t in teachers" :key="t.id" :label="`${t.name}（${t.username}）`" :value="t.id" />
        </el-select>
        <el-button type="primary" @click="addTeacher">添加</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { studentApi, adminApi } from '../../api'
import { isSchoolAdmin, isPlatformAdmin } from '../../utils/auth'

// 学校管理员 / 平台超管可管理班级（新增/删除/配置班主任与科任）；教师仅可查看
const isAdmin = isSchoolAdmin() || isPlatformAdmin()
const items = ref([])
const teachers = ref([])
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const graduatedFilter = ref('false')
const form = reactive({ name: '', code: '', major: '', grade: '一年级', teacher_id: null, is_graduated: false })
// 科任老师管理
const teacherDialog = ref(false)
const currentClass = ref(null)
const classTeacherList = ref([])
const newTeacherId = ref(null)

onMounted(async () => {
  // 管理员加载教师列表（用于指定班主任）
  if (isAdmin) {
    try {
      const res = await adminApi.users({ role: 'teacher' })
      teachers.value = res.items || []
    } catch (e) {
      console.error('[Classrooms] 加载教师列表失败:', e)
    }
  }
  load()
})

async function load() {
  loading.value = true
  try {
    const res = await studentApi.classrooms({ graduated: graduatedFilter.value })
    items.value = res.items
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { name: '', code: '', major: '', grade: '一年级', teacher_id: null, is_graduated: false })
  dialog.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, { name: row.name, code: row.code, major: row.major, grade: row.grade, teacher_id: row.teacher_id, is_graduated: !!row.is_graduated })
  dialog.value = true
}

async function save() {
  if (!form.name || !form.code) return ElMessage.warning('请填写名称和代码')
  saving.value = true
  try {
    const payload = { name: form.name, code: form.code, major: form.major, grade: form.grade, is_graduated: !!form.is_graduated }
    // 教师编辑时不提交 teacher_id（后端也会拒绝），管理员提交
    if (isAdmin) payload.teacher_id = form.teacher_id
    if (editing.value) await studentApi.updateClassroom(editing.value.id, payload)
    else await studentApi.createClassroom(payload)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除班级「${row.name}」吗？`, '提示', { type: 'warning' })
  await studentApi.deleteClassroom(row.id)
  ElMessage.success('删除成功')
  load()
}

function openTeachers(row) {
  currentClass.value = row
  newTeacherId.value = null
  teacherDialog.value = true
  loadClassTeachers()
}

async function loadClassTeachers() {
  try {
    const res = await studentApi.classTeachers(currentClass.value.id)
    classTeacherList.value = res.items || []
  } catch (e) {
  }
}

async function addTeacher() {
  if (!newTeacherId.value) return ElMessage.warning('请选择教师')
  try {
    await studentApi.addClassTeacher(currentClass.value.id, { teacher_id: newTeacherId.value })
    ElMessage.success('添加成功')
    newTeacherId.value = null
    loadClassTeachers()
  } catch (e) {
  }
}

async function removeTeacher(t) {
  await ElMessageBox.confirm(`确定移除科任老师「${t.name}」吗？`, '提示', { type: 'warning' })
  try {
    await studentApi.removeClassTeacher(currentClass.value.id, t.teacher_id)
    ElMessage.success('已移除')
    loadClassTeachers()
  } catch (e) {
  }
}
</script>

<style scoped>
.teacher-list {
  max-height: 240px;
  overflow-y: auto;
}
.teacher-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 4px;
  border-bottom: 1px solid #f0f0f0;
}
.teacher-name {
  flex: 1;
}
.teacher-add {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
</style>
