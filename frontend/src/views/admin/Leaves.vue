<template>
  <div>
    <div class="toolbar">
      <el-select
        v-model="status"
        placeholder="全部状态"
        clearable
        style="width: 140px"
        @change="reload"
      >
        <el-option label="登记" value="登记" />
        <el-option label="已销假" value="已销假" />
      </el-select>
      <StudentSelect
        v-model="studentId"
        v-model:class-id="classId"
        show-class-filter
        placeholder="按学生筛选"
        style="width: 320px"
        @update:model-value="reload"
        @update:class-id="reload"
      />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">登记请假</el-button>
      <SortBar v-model="order" />
    </div>

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="6"
        empty-description="暂无请假记录"
        @retry="load"
      >
        <template #empty>
          <el-button type="primary" @click="openCreate">登记请假</el-button>
        </template>
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column label="学生" width="120">
            <template #default="{ row }">
              <el-link type="primary" :underline="false" @click="openStudentCard(row)">{{
                row.student_name
              }}</el-link>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="事由" min-width="180" />
          <el-table-column prop="start_date" label="开始日期" width="120" />
          <el-table-column prop="end_date" label="结束日期" width="120" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === '已销假' ? 'success' : 'warning'" size="small">{{
                row.status
              }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status !== '已销假'" link type="success" @click="finish(row)"
                >销假</el-button
              >
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

    <el-dialog v-model="dialog" :title="editing ? '编辑请假' : '登记请假'" width="460px">
      <el-form label-width="80px">
        <el-form-item label="学生" required>
          <!-- 编辑态不可改学生：后端 LeaveUpdate 无 student_id，改了静默无效 -->
          <StudentSelect v-model="form.student_id" show-class-filter :disabled="!!editing" />
        </el-form-item>
        <el-form-item label="事由"><el-input v-model="form.reason" /></el-form-item>
        <el-form-item label="开始日期"
          ><el-date-picker
            v-model="form.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
        /></el-form-item>
        <el-form-item label="结束日期"
          ><el-date-picker
            v-model="form.end_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
        /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <StudentCard v-model:visible="studentCardVisible" :student-id="studentCardId" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import StudentSelect from '../../components/StudentSelect.vue'
import SortBar from '../../components/SortBar.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import StudentCard from '../../components/StudentCard.vue'
import StateView from '../../components/StateView.vue'
import { useSort } from '../../composables/useSort.js'
import { useCrudList } from '../../composables/useCrudList'
import { leaveApi } from '../../api'

const { order, useSorted } = useSort('leaves')
const status = ref('')
const studentId = ref(null)
const classId = ref(null)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
// 销假的重入锁：防止双击重复写库（进入即置位、finally 复位）
const finishing = ref(false)
const form = reactive({ student_id: null, reason: '', start_date: '', end_date: '' })
const {
  items: rawItems,
  page,
  pageSize,
  total,
  loading,
  error,
  load,
  reload,
  remove,
} = useCrudList(leaveApi.list, {
  removeApi: leaveApi.remove,
  buildParams: () => ({
    status: status.value,
    student_id: studentId.value,
    class_id: classId.value,
  }),
  removeTip: () => '确定删除该记录吗？',
})
const items = useSorted(rawItems)

// 跨模块学生卡片
const studentCardVisible = ref(false)
const studentCardId = ref(null)
function openStudentCard(row) {
  if (!row.student_id) return
  studentCardId.value = row.student_id
  studentCardVisible.value = true
}

onMounted(load)

function openCreate() {
  editing.value = null
  Object.assign(form, { student_id: null, reason: '', start_date: '', end_date: '' })
  dialog.value = true
}

function openEdit(row) {
  editing.value = row
  // 只拷贝表单声明的字段，避免整行的 status / student_name 等额外键动态注入 reactive
  Object.assign(form, {
    student_id: row.student_id,
    reason: row.reason,
    start_date: row.start_date,
    end_date: row.end_date,
  })
  dialog.value = true
}

async function save() {
  if (!form.student_id) return ElMessage.warning('请选择学生')
  saving.value = true
  try {
    // 显式构造载荷：openEdit 的 Object.assign(form, row) 会把 row 的 status 等键
    // 动态注入 reactive；若整个 form 直接提交，"编辑已销假后再登记请假"会残留
    // status="已销假" 被后端 LeaveCreate.status 接收、把新记录写成已销假。
    const payload = {
      student_id: form.student_id,
      reason: form.reason,
      start_date: form.start_date,
      end_date: form.end_date,
    }
    if (editing.value) await leaveApi.update(editing.value.id, payload)
    else await leaveApi.create(payload)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function finish(row) {
  if (finishing.value) return // 防双击：写入在途时忽略重复触发
  finishing.value = true
  try {
    await leaveApi.update(row.id, { status: '已销假' })
    ElMessage.success('已销假')
    load()
  } finally {
    finishing.value = false
  }
}
</script>
