<template>
  <div>
    <!-- 教师行为统计（产品化洞察） -->
    <div class="page-card stats-card">
      <div class="stats-head">
        <h3 class="stats-title">
          教师行为统计
          <span class="stats-sub"
            >（近 {{ stats.days || 30 }} 天，共 {{ stats.total || 0 }} 条操作）</span
          >
        </h3>
      </div>
      <div class="stats-grid">
        <div class="stats-col">
          <div class="stats-col-title">教师活跃度 Top</div>
          <div v-if="stats.by_teacher?.length" class="stats-list">
            <div
              v-for="(t, i) in stats.by_teacher.slice(0, 10)"
              :key="t.username"
              class="stats-row"
            >
              <span class="rank">{{ i + 1 }}</span>
              <span class="name">{{ t.username }}</span>
              <el-progress
                :percentage="teacherPercent(t.count)"
                :stroke-width="8"
                :show-text="false"
                class="bar"
              />
              <span class="num">{{ t.count }}</span>
            </div>
          </div>
          <div v-else class="empty-state">暂无数据</div>
        </div>
        <div class="stats-col">
          <div class="stats-col-title">操作类型分布</div>
          <div v-if="stats.by_action?.length" class="stats-list">
            <div v-for="a in stats.by_action.slice(0, 10)" :key="a.action" class="stats-row">
              <span class="name">{{ actionText(a.action) }}</span>
              <el-progress
                :percentage="actionPercent(a.count)"
                :stroke-width="8"
                :show-text="false"
                class="bar"
              />
              <span class="num">{{ a.count }}</span>
            </div>
          </div>
          <div v-else class="empty-state">暂无数据</div>
        </div>
      </div>
    </div>

    <div class="toolbar">
      <el-select
        v-model="action"
        placeholder="全部操作"
        clearable
        filterable
        style="width: 200px"
        @change="reload"
      >
        <el-option v-for="a in actions" :key="a" :label="actionText(a)" :value="a" />
      </el-select>
      <el-input
        v-model="keyword"
        placeholder="搜索学生姓名"
        clearable
        style="width: 200px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-date-picker
        v-model="date"
        type="date"
        placeholder="选择日期"
        value-format="YYYY-MM-DD"
        clearable
        style="width: 160px"
        @change="reload"
      />
      <el-button @click="reload">查询</el-button>
      <div class="spacer"></div>
    </div>

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="7"
        empty-description="暂无审计日志"
        @retry="load"
      >
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
      </StateView>
      <PaginationBar
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="total"
        @change="load"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useDebouncedRef } from '../../composables/useDebouncedRef'
import PaginationBar from '../../components/PaginationBar.vue'
import StateView from '../../components/StateView.vue'
import { useCrudList } from '../../composables/useCrudList'
import { adminApi } from '../../api'

const stats = ref({ by_teacher: [], by_action: [], by_day: [], total: 0, days: 30 })
const action = ref('')
const keyword = useDebouncedRef('', 300)
const date = ref('')
const actions = ref([])
const { items, page, pageSize, total, loading, error, load, reload } = useCrudList(
  adminApi.auditLogs,
  {
    buildParams: () => ({
      action: action.value,
      keyword: keyword.value,
      date: date.value,
    }),
  }
)
watch(keyword, reload)

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
  upgrade_grade: '年级升级',
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
    console.error('[AuditLogs] 加载操作类型失败:', e)
  }
  load()
  loadStats()
})

async function loadStats() {
  try {
    stats.value = await adminApi.auditLogStats({ days: 30 })
  } catch (e) {
    console.error('[AuditLogs] 加载行为统计失败:', e)
  }
}

// 教师活跃度百分比（相对最高值）
function teacherPercent(count) {
  const max = stats.value.by_teacher?.[0]?.count || 1
  return Math.round((count / max) * 100)
}

// 操作类型百分比（相对最高值）
function actionPercent(count) {
  const max = stats.value.by_action?.[0]?.count || 1
  return Math.round((count / max) * 100)
}
</script>

<style scoped>
.stats-card {
  margin-bottom: 16px;
}
.stats-head {
  margin-bottom: 12px;
}
.stats-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.stats-sub {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-tertiary);
  margin-left: 6px;
}
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}
.stats-col-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
.stats-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stats-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.stats-row .rank {
  width: 18px;
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: center;
}
.stats-row .name {
  min-width: 80px;
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
}
.stats-row .bar {
  flex: 1;
}
.stats-row .num {
  width: 36px;
  text-align: right;
  font-size: 12px;
  color: var(--text-tertiary);
}
@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
