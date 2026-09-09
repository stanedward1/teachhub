<template>
  <div>
    <div class="toolbar">
      <el-select v-model="action" placeholder="全部操作" clearable filterable style="width: 200px" @change="load">
        <el-option v-for="a in actions" :key="a" :label="actionText(a)" :value="a" />
      </el-select>
      <el-input v-model="keyword" placeholder="搜索学生姓名" clearable style="width: 200px" @keyup.enter="load" @clear="load" />
      <el-date-picker
        v-model="date"
        type="date"
        placeholder="选择日期"
        value-format="YYYY-MM-DD"
        clearable
        style="width: 160px"
        @change="onDateChange"
      />
      <el-button @click="load">查询</el-button>
      <div class="spacer"></div>
    </div>

    <div class="page-card">
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="操作人" width="120" />
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="roleType(row.role)" size="small">{{ roleText(row.role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <span>{{ actionText(row.action) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="target" label="操作对象" min-width="200" show-overflow-tooltip />
        <el-table-column prop="detail" label="详情" min-width="180" show-overflow-tooltip />
        <el-table-column prop="created_at" label="时间" width="170" />
      </el-table>
      <el-pagination
        style="margin-top: 16px; justify-content: flex-end"
        layout="total, prev, pager, next"
        :total="total" :page-size="pageSize" :current-page="page"
        @current-change="onPage"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useDebouncedRef } from '../../composables/useDebouncedRef'
import { adminApi } from '../../api'

const items = ref([])
const action = ref('')
const keyword = useDebouncedRef('', 300)
watch(keyword, () => load())
const date = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)
const actions = ref([])

// 操作类型 -> 中文（覆盖后端全部 64 种操作）
const ACTION_CN = {
  // 账号
  create_user: '创建账号',
  update_user: '编辑账号',
  delete_user: '删除账号',
  change_password: '修改密码',
  reset_password: '重置密码',
  reset_student_password: '重置学生密码',
  // 学校/班级
  create_school: '创建学校',
  update_school: '编辑学校',
  delete_school: '删除学校',
  create_classroom: '创建班级',
  update_classroom: '编辑班级',
  delete_classroom: '删除班级',
  // 学生
  create_student: '创建学生',
  update_student: '编辑学生',
  delete_student: '删除学生',
  import_students: '导入学生',
  upload_student_avatar: '上传学生头像',
  add_student_tag: '添加学生标签',
  remove_student_tag: '删除学生标签',
  // 成绩/考勤/积分/沟通
  create_score: '录入成绩',
  update_score: '编辑成绩',
  delete_score: '删除成绩',
  import_scores: '导入成绩',
  create_leave: '登记请假',
  update_leave: '编辑请假',
  delete_leave: '删除请假',
  create_point: '登记积分',
  delete_point: '删除积分',
  create_communication: '新增沟通',
  delete_communication: '删除沟通',
  // 资源/试卷/座位/周报
  create_resource: '新增资源',
  delete_resource: '删除资源',
  upload_exam: '上传试卷',
  update_exam: '编辑试卷',
  delete_exam: '删除试卷',
  save_seat: '保存座位表',
  save_report: '保存周报',
  delete_report: '删除周报',
  // 班级日志
  create_work_log: '新增工作日志',
  update_work_log: '编辑工作日志',
  delete_work_log: '删除工作日志',
  create_plan: '新增计划',
  update_plan: '编辑计划',
  delete_plan: '删除计划',
  create_schedule: '新增课表',
  delete_schedule: '删除课表',
  create_activity: '新增活动',
  delete_activity: '删除活动',
  create_talk: '新增谈心',
  delete_talk: '删除谈心',
  create_return_record: '新增返校记录',
  delete_return_record: '删除返校记录',
  create_performance: '新增表现记录',
  delete_performance: '删除表现记录',
  create_student_comment: '新增评语',
  update_student_comment: '编辑评语',
  delete_student_comment: '删除评语',
  // 作业
  create_assignment: '布置作业',
  update_assignment: '编辑作业',
  delete_assignment: '删除作业',
  mark_excellent: '评选优秀',
  unmark_excellent: '取消优秀',
  add_submission_comment: '提交点评',
  delete_submission_comment: '删除点评',
  // 系统
  upgrade_grade: '年级升级'
}

function actionText(a) {
  return ACTION_CN[a] || a
}

function roleText(r) {
  return { admin: '管理员', teacher: '教师', student: '学生' }[r] || r
}
function roleType(r) {
  return { admin: 'danger', teacher: 'primary', student: 'info' }[r] || 'info'
}

onMounted(async () => {
  // 动态加载全部操作类型（后端去重返回）
  try {
    const res = await adminApi.auditLogActions()
    actions.value = res.items || []
  } catch (e) {
    actions.value = Object.keys(ACTION_CN)
  }
  load()
})

async function load() {
  loading.value = true
  try {
    const res = await adminApi.auditLogs({ action: action.value, keyword: keyword.value, date: date.value, page: page.value, page_size: pageSize })
    items.value = res.items
    total.value = res.total
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function onDateChange() {
  page.value = 1
  load()
}

function onPage(p) {
  page.value = p
  load()
}
</script>
