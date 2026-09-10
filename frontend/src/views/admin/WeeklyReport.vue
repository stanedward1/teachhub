<template>
  <div>
    <div class="toolbar">
      <el-select v-model="classId" placeholder="选择班级" style="width: 200px" @change="onClassChange">
        <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-date-picker
        v-model="dateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        style="width: 260px"
        @change="loadWeeklyData"
      />
      <el-button @click="loadWeeklyData" :disabled="!classId">查询数据</el-button>
      <div class="spacer"></div>
      <el-button type="primary" @click="generateReport" :disabled="!weeklyData">生成周报</el-button>
      <el-button @click="loadHistory">历史报告</el-button>
    </div>

    <!-- 数据概览面板 -->
    <div class="page-card" v-if="weeklyData">
      <h3 class="card-title">班级数据概览</h3>
      <el-row :gutter="16">
        <el-col :xs="12" :sm="6" v-for="s in dataCards" :key="s.label">
          <div class="data-card">
            <div class="data-card-value">{{ s.value }}</div>
            <div class="data-card-label">{{ s.label }}</div>
          </div>
        </el-col>
      </el-row>
      <!-- 积分排行 -->
      <el-row :gutter="16" style="margin-top: 16px;">
        <el-col :xs="24" :md="12">
          <div class="card-title">积分 TOP 5</div>
          <div v-for="(s, i) in weeklyData.top5" :key="i" class="rank-item">
            <span class="rank-num" :class="'rank-' + (i + 1)">{{ i + 1 }}</span>
            <span>{{ s.name }}</span>
            <span class="rank-points">+{{ s.points }}</span>
          </div>
          <div v-if="!weeklyData.top5.length" class="empty-state">暂无数据</div>
        </el-col>
        <el-col :xs="24" :md="12">
          <div class="card-title">待关注学生</div>
          <div v-for="(s, i) in weeklyData.bottom5" :key="i" class="rank-item">
            <span class="rank-num warn">{{ i + 1 }}</span>
            <span>{{ s.name }}</span>
            <span class="rank-points" style="color: #ef4444;">{{ s.points }}</span>
          </div>
          <div v-if="!weeklyData.bottom5.length" class="empty-state">暂无数据</div>
        </el-col>
      </el-row>
      <!-- 近期表现 -->
      <div style="margin-top: 16px;" v-if="weeklyData.recent_performances?.length">
        <div class="card-title">近期表现记录</div>
        <el-table :data="weeklyData.recent_performances" size="small" max-height="240">
          <el-table-column prop="student_name" label="学生" width="100" />
          <el-table-column label="类型" width="80">
            <template #default="{ row }">
              <el-tag :type="row.ptype === '积极' ? 'success' : 'danger'" size="small">{{ row.ptype }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="content" label="内容" min-width="200" />
        </el-table>
      </div>
    </div>

    <!-- 报告编辑区 -->
    <div class="page-card" v-if="reportContent !== null">
      <h3 class="card-title">报告编辑</h3>
      <el-input v-model="reportTitle" placeholder="报告标题" style="margin-bottom: 12px; font-size: 16px; font-weight: 600;" />
      <el-input
        v-model="reportContent"
        type="textarea"
        :rows="16"
        placeholder="报告内容将根据数据自动生成，您也可以手动编辑..."
      />
      <div style="margin-top: 12px; display: flex; gap: 8px;">
        <el-button type="primary" :loading="saving" @click="saveReport">保存报告</el-button>
        <el-button @click="previewReport">预览</el-button>
      </div>
    </div>

    <!-- 历史报告弹窗 -->
    <el-dialog v-model="historyDialog" title="历史报告" width="700px">
      <el-table :data="historyItems" max-height="400">
        <el-table-column prop="title" label="标题" min-width="200" />
        <el-table-column prop="class_name" label="班级" width="140" />
        <el-table-column prop="week_start" label="周期" width="200">
          <template #default="{ row }">{{ row.week_start }} ~ {{ row.week_end }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewReport(row)">查看</el-button>
            <el-button link type="danger" @click="deleteReport(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 预览弹窗 -->
    <el-dialog v-model="previewDialog" title="报告预览" width="760px" fullscreen>
      <div class="md-body" v-html="previewHtml"></div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { reportApi, studentApi } from '../../api'

const classes = ref([])
const classId = ref(null)
const dateRange = ref(null)
const weeklyData = ref(null)
const reportContent = ref(null)
const reportTitle = ref('')
const saving = ref(false)

const historyDialog = ref(false)
const historyItems = ref([])
const previewDialog = ref(false)
const previewHtml = ref('')

const dataCards = computed(() => {
  if (!weeklyData.value) return []
  const d = weeklyData.value
  return [
    { label: '班级人数', value: d.total_students },
    { label: '出勤率', value: d.attendance_rate + '%' },
    { label: '请假人次', value: d.leave_count },
    { label: '积极表现', value: d.positive_count },
    { label: '消极表现', value: d.negative_count },
    { label: '成绩均分', value: d.score_avg || '—' },
    { label: '成绩条数', value: d.score_count },
    { label: '积分排行', value: d.top5?.length ? d.top5[0].name : '—' },
  ]
})

onMounted(async () => {
  // 管理员看全部，教师只看自己负责的班级
  const res = await studentApi.classrooms()
  classes.value = res.items
})

function onClassChange() {
  weeklyData.value = null
  reportContent.value = null
}

async function loadWeeklyData() {
  if (!classId.value) return
  try {
    const [start, end] = dateRange.value || ['', '']
    weeklyData.value = await reportApi.weeklyData({ class_id: classId.value, week_start: start, week_end: end })
  } catch (e) {
  }
}

function generateReport() {
  if (!weeklyData.value) return
  const d = weeklyData.value
  const cls = classes.value.find(c => c.id === classId.value)
  const [start, end] = dateRange.value || ['', '']

  reportTitle.value = `${cls?.name || ''}班级周报（${start} ~ ${end}）`
  reportContent.value = `# ${cls?.name || ''}班级周报

> 周期：${start} ~ ${end} ｜ 班级人数：${d.total_students} 人

## 一、本周概况

- **出勤率**：${d.attendance_rate}%
- **请假人次**：${d.leave_count} 人次
- **积极表现**：${d.positive_count} 次
- **消极表现**：${d.negative_count} 次
- **成绩均分**：${d.score_avg || '暂无'}（共 ${d.score_count} 条记录）

## 二、积分排行 TOP 5

${d.top5?.length ? d.top5.map((s, i) => `${i + 1}. ${s.name}：+${s.points} 分`).join('\n') : '暂无数据'}

## 三、待关注学生

${d.bottom5?.length ? d.bottom5.map((s, i) => `${i + 1}. ${s.name}：${s.points} 分`).join('\n') : '暂无数据'}

## 四、学生表现记录

${d.recent_performances?.length ? d.recent_performances.map(p => `- **${p.student_name}**：${p.ptype === '积极' ? '✅' : '⚠️'} ${p.content}`).join('\n') : '暂无记录'}

## 五、学生画像概要

${d.profile_summaries?.length ? d.profile_summaries.map(s => `- ${s.name}（${s.student_no}）：积分 ${s.points}，请假 ${s.leave_count} 次，积极 ${s.positive} 次，消极 ${s.negative} 次`).join('\n') : '暂无数据'}

## 六、本周总结与下周计划

> 请教师在此处填写总结与计划...
`
}

async function saveReport() {
  if (!reportTitle.value.trim()) return ElMessage.warning('请输入报告标题')
  saving.value = true
  try {
    const [start, end] = dateRange.value || ['', '']
    await reportApi.save({
      class_id: classId.value,
      title: reportTitle.value.trim(),
      content: reportContent.value,
      week_start: start,
      week_end: end,
      data_snapshot: weeklyData.value,
    })
    ElMessage.success('报告保存成功')
  } catch (e) {
  } finally {
    saving.value = false
  }
}

function previewReport() {
  if (!reportContent.value) return
  const html = marked.parse(reportContent.value, { breaks: true })
  previewHtml.value = DOMPurify.sanitize(html)
  previewDialog.value = true
}

async function loadHistory() {
  try {
    const res = await reportApi.list(classId.value ? { class_id: classId.value } : {})
    historyItems.value = res.items
    historyDialog.value = true
  } catch (e) {
  }
}

function viewReport(row) {
  reportTitle.value = row.title
  reportContent.value = row.content || ''
  historyDialog.value = false
}

async function deleteReport(row) {
  await ElMessageBox.confirm(`确定删除报告「${row.title}」吗？`, '提示', { type: 'warning' })
  await reportApi.remove(row.id)
  ElMessage.success('删除成功')
  loadHistory()
}
</script>

<style scoped>
.data-card {
  background: #f8fafc;
  border-radius: var(--radius-md);
  padding: 14px;
  text-align: center;
  margin-bottom: 8px;
}
.data-card-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}
.data-card-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.rank-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-light);
  font-size: 13px;
}
.rank-num {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: #2563eb;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  margin-right: 10px;
}
.rank-num.rank-1 { background: #f59e0b; }
.rank-num.rank-2 { background: #94a3b8; }
.rank-num.rank-3 { background: #d97706; }
.rank-num.warn { background: #ef4444; }
.rank-points {
  margin-left: auto;
  font-weight: 600;
  color: #10b981;
}
</style>