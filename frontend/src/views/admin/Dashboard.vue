<template>
  <div>
    <!-- 首屏骨架屏 / 加载失败重试 -->
    <StateView :loading="loading" :error="error" error-description="看板数据加载失败" @retry="load">
      <template #skeleton>
        <el-skeleton :rows="10" animated />
      </template>
      <!-- 教师身份标识（班主任 / 科任） -->
      <div
        v-if="identity.head_classes?.length || identity.subject_classes?.length"
        class="identity-bar"
      >
        <el-tag
          v-for="c in identity.head_classes"
          :key="'h' + c"
          type="warning"
          effect="dark"
          size="small"
          style="margin-right: 6px"
          >班主任 · {{ c }}</el-tag
        >
        <el-tag
          v-for="c in identity.subject_classes"
          :key="'s' + c"
          type="info"
          effect="dark"
          size="small"
          style="margin-right: 6px"
          >科任 · {{ c }}</el-tag
        >
      </div>

      <!-- 统计卡片（可点击跳转） -->
      <el-row :gutter="16" class="stat-row">
        <el-col v-for="s in stats" :key="s.label" :xs="12" :sm="6" :lg="3">
          <div class="stat-card" @click="navigateTo(s.route)">
            <div class="stat-icon-box" :style="{ background: s.bg }">
              <el-icon class="stat-icon"><component :is="s.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ s.value }}</div>
              <div class="stat-label">{{ s.label }}</div>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- 请假趋势图表 + 详情 -->
      <div class="page-card chart-card">
        <h3 class="card-title">近 7 天请假趋势</h3>
        <div ref="trendRef" style="width: 100%; height: 280px"></div>
        <!-- 请假人员详情 -->
        <div v-if="leaveDetailDays.length" style="margin-top: 16px">
          <el-collapse>
            <el-collapse-item
              v-for="day in leaveDetailDays"
              :key="day.date"
              :title="`${day.date} 日 — ${day.count} 人请假`"
            >
              <el-table :data="day.items" size="small" v-if="day.items.length">
                <el-table-column prop="class_name" label="班级" width="130" />
                <el-table-column prop="name" label="姓名" width="100" />
                <el-table-column prop="reason" label="请假原因" min-width="160" />
                <el-table-column label="时长" width="80">
                  <template #default="{ row }">{{ row.duration }} 天</template>
                </el-table-column>
                <el-table-column label="时间段" width="220">
                  <template #default="{ row }">{{ row.start }} ~ {{ row.end }}</template>
                </el-table-column>
              </el-table>
              <div v-else style="color: #9ca3af; padding: 8px">暂无记录</div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>

      <!-- 出勤率 -->
      <div class="page-card chart-card">
        <div class="chart-head">
          <h3 class="card-title">近 7 天出勤率</h3>
          <div class="att-head">
            <span class="att-rate">{{ data.attendance?.rate ?? 0 }}%</span>
            <span class="att-status">
              <el-tag
                v-for="(v, k) in data.attendance?.status || {}"
                :key="k"
                size="small"
                effect="plain"
                style="margin-left: 6px"
              >
                {{ k }} {{ v }}
              </el-tag>
            </span>
          </div>
        </div>
        <div ref="attRef" style="width: 100%; height: 220px"></div>
      </div>

      <!-- 各班出勤率 -->
      <div class="page-card chart-card">
        <h3 class="card-title">各班出勤率</h3>
        <el-table :data="data.attendance?.by_class || []" size="small" style="margin-top: 8px">
          <el-table-column prop="class_name" label="班级" min-width="140" />
          <el-table-column label="出勤率" min-width="180">
            <template #default="{ row }">
              <el-progress
                v-if="row.total"
                :percentage="row.rate"
                :stroke-width="10"
                :color="attRateColor(row.rate)"
              />
              <span v-else style="color: #9ca3af; font-size: 12px">未点名</span>
            </template>
          </el-table-column>
          <el-table-column label="出勤 / 缺勤 / 请假 / 迟到" min-width="220">
            <template #default="{ row }">
              {{ row.status['出勤'] }} / {{ row.status['缺勤'] }} / {{ row.status['请假'] }} /
              {{ row.status['迟到'] }}
            </template>
          </el-table-column>
        </el-table>
        <div v-if="!data.attendance?.by_class?.length" class="empty-state">暂无考勤数据</div>
      </div>

      <!-- 成绩分布（按考试名称） -->
      <div class="page-card chart-card">
        <div class="chart-head">
          <h3 class="card-title">成绩分布</h3>
          <el-select
            v-model="selectedExam"
            placeholder="全部考试"
            clearable
            style="width: 200px"
            @change="renderCharts"
          >
            <el-option v-for="e in examNames" :key="e" :label="e" :value="e" />
          </el-select>
        </div>
        <div ref="distRef" style="width: 100%; height: 300px"></div>
      </div>

      <!-- 异常预警（可行动的洞察） -->
      <div v-if="hasAlerts" class="page-card">
        <h3 class="card-title">异常预警</h3>
        <div class="alert-group">
          <div v-if="alerts.absenteeism?.length" class="alert-block">
            <div class="alert-head">
              <el-icon color="#dc2626"><WarningFilled /></el-icon
              ><span class="alert-title">连续缺勤</span
              ><span class="alert-count">{{ alerts.absenteeism.length }}</span>
            </div>
            <div class="alert-tags">
              <el-tag
                v-for="a in alerts.absenteeism"
                :key="a.student_id"
                type="danger"
                effect="plain"
                size="small"
              >
                {{ a.name }}（{{ a.class_name }}）缺勤 {{ a.count }} 次
              </el-tag>
            </div>
          </div>
          <div v-if="alerts.score_drop?.length" class="alert-block">
            <div class="alert-head">
              <el-icon color="#f59e0b"><TrendCharts /></el-icon
              ><span class="alert-title">成绩骤降</span
              ><span class="alert-count">{{ alerts.score_drop.length }}</span>
            </div>
            <div class="alert-tags">
              <el-tag
                v-for="a in alerts.score_drop"
                :key="a.student_id"
                type="warning"
                effect="plain"
                size="small"
              >
                {{ a.name }}（{{ a.class_name }}）{{ a.subject }} 降 {{ a.drop }} 分
              </el-tag>
            </div>
          </div>
          <div v-if="alerts.pending_leave?.length" class="alert-block">
            <div class="alert-head">
              <el-icon color="#2563eb"><Bell /></el-icon><span class="alert-title">待处理请假</span
              ><span class="alert-count">{{ alerts.pending_leave.length }}</span>
            </div>
            <div class="alert-tags">
              <el-tag
                v-for="a in alerts.pending_leave"
                :key="a.leave_id"
                type="primary"
                effect="plain"
                size="small"
              >
                {{ a.name }}（{{ a.class_name }}）{{ a.reason }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>

      <!-- 最近动态 -->
      <div class="page-card">
        <h3 class="card-title">最近班级动态</h3>
        <el-timeline v-if="data.recent?.length" style="margin-top: 8px">
          <el-timeline-item
            v-for="(r, i) in data.recent"
            :key="i"
            :timestamp="r.time"
            placement="top"
          >
            <el-tag
              size="small"
              :type="r.type === '请假' ? 'warning' : 'info'"
              effect="plain"
              style="margin-right: 8px"
              >{{ r.type }}</el-tag
            >
            {{ r.text }}
          </el-timeline-item>
        </el-timeline>
        <div v-else class="empty-state">暂无动态</div>
      </div>
    </StateView>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts/core'
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([LineChart, PieChart, GridComponent, TooltipComponent, TitleComponent, CanvasRenderer])
import { adminApi } from '../../api'
import { isPlatformAdmin } from '../../utils/auth'
import StateView from '../../components/StateView.vue'

const router = useRouter()
const data = ref({
  counts: {},
  leave_trend: [],
  leave_details: [],
  score_dist: {},
  score_dist_by_exam: {},
  recent: [],
  attendance: {},
  identity: {},
})
const loading = ref(true)
const error = ref(false)
const trendRef = ref(null)
const distRef = ref(null)
const attRef = ref(null)
const selectedExam = ref('')
let trendChart = null
let distChart = null
let attChart = null
let resizeTimer = null

// 考试名称列表（用于下拉选择）
const examNames = computed(() => Object.keys(data.value.score_dist_by_exam || {}))

// 当前要展示的成绩分布数据
const currentDist = computed(() => {
  const byExam = data.value.score_dist_by_exam || {}
  if (selectedExam.value && byExam[selectedExam.value]) {
    return byExam[selectedExam.value]
  }
  return data.value.score_dist || {}
})

const statCards = [
  {
    icon: 'User',
    bg: 'linear-gradient(135deg, #2563eb, #4f46e5)',
    key: 'student',
    route: '/admin/students',
  },
  {
    icon: 'School',
    bg: 'linear-gradient(135deg, #0ea5e9, #0284c7)',
    key: 'class',
    route: '/admin/classrooms',
  },
  {
    icon: 'Document',
    bg: 'linear-gradient(135deg, #8b5cf6, #7c3aed)',
    key: 'assignment',
    route: '/admin/homework',
  },
  {
    icon: 'Upload',
    bg: 'linear-gradient(135deg, #f59e0b, #d97706)',
    key: 'submission',
    route: '/admin/homework',
  },
  {
    icon: 'Calendar',
    bg: 'linear-gradient(135deg, #ef4444, #dc2626)',
    key: 'leave',
    route: '/admin/leaves',
  },
  {
    icon: 'Folder',
    bg: 'linear-gradient(135deg, #10b981, #059669)',
    key: 'resource',
    route: '/admin/resources',
  },
  {
    icon: 'Tickets',
    bg: 'linear-gradient(135deg, #f43f5e, #e11d48)',
    key: 'exam',
    route: '/admin/exams',
  },
  {
    icon: 'Bell',
    bg: 'linear-gradient(135deg, #64748b, #475569)',
    key: 'today_leave',
    route: '/admin/leaves',
  },
]

const stats = computed(() => {
  const c = data.value.counts || {}
  // 「教学资源 / 试卷数」在模型上只有 school_id、**没有班级归属**，是校级（超管为全平台）
  // 资产库，因此它们的层级与同屏的「学生总数 / 提交总数（本班口径）」不同。
  // 把层级写进文案，避免教师把全校数误当成自己班的数。
  const assetScope = isPlatformAdmin() ? '全平台' : '全校'
  return statCards.map((s) => ({
    label: {
      student: '学生总数',
      class: '班级数',
      assignment: '作业任务',
      submission: '提交总数',
      leave: '请假记录',
      resource: `教学资源（${assetScope}）`,
      exam: `试卷数（${assetScope}）`,
      today_leave: '今日请假',
    }[s.key],
    value: c[s.key] || 0,
    icon: s.icon,
    bg: s.bg,
    route: s.route,
  }))
})

const leaveDetailDays = computed(() => data.value.leave_details || [])
const identity = computed(() => data.value.identity || {})

// 异常预警数据
const alerts = computed(
  () => data.value.alerts || { absenteeism: [], score_drop: [], pending_leave: [] }
)
const hasAlerts = computed(() => {
  const a = alerts.value
  return (
    (a.absenteeism?.length || 0) + (a.score_drop?.length || 0) + (a.pending_leave?.length || 0) > 0
  )
})

function navigateTo(route) {
  if (route) router.push(route)
}

function attRateColor(rate) {
  if (rate >= 95) return '#16a34a'
  if (rate >= 85) return '#f59e0b'
  return '#dc2626'
}

onMounted(() => {
  window.addEventListener('resize', resize)
  load()
})

async function load() {
  loading.value = true
  error.value = false
  try {
    data.value = await adminApi.dashboard()
  } catch (e) {
    error.value = true
    console.error('[Dashboard] 加载看板数据失败:', e)
  } finally {
    loading.value = false
  }
  await nextTick()
  setTimeout(() => renderCharts(), 0)
}

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  clearTimeout(resizeTimer)
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
  if (distChart) {
    distChart.dispose()
    distChart = null
  }
  if (attChart) {
    attChart.dispose()
    attChart = null
  }
})

function resize() {
  clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    trendChart?.resize()
    distChart?.resize()
    attChart?.resize()
  }, 100)
}

function renderCharts() {
  if (trendRef.value) {
    if (trendChart) trendChart.dispose()
    trendChart = echarts.init(trendRef.value)
    trendChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 20, top: 20, bottom: 30 },
      xAxis: {
        type: 'category',
        data: (data.value.leave_trend || []).map((t) => t.date),
        axisLine: { lineStyle: { color: '#e5e7eb' } },
        axisTick: { show: false },
        axisLabel: { color: '#9ca3af', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        splitLine: { lineStyle: { color: '#f3f4f6' } },
        axisLabel: { color: '#9ca3af', fontSize: 11 },
      },
      series: [
        {
          type: 'line',
          smooth: true,
          data: (data.value.leave_trend || []).map((t) => t.count),
          areaStyle: { color: 'rgba(37,99,235,0.15)' },
          lineStyle: { color: '#2563eb', width: 2 },
          itemStyle: { color: '#2563eb' },
          symbol: 'circle',
          symbolSize: 6,
        },
      ],
    })
  }

  if (distRef.value) {
    if (distChart) distChart.dispose()
    distChart = echarts.init(distRef.value)
    const dist = currentDist.value || {}
    const distData = Object.entries(dist).map(([name, val]) => ({
      name,
      value: val.count || 0,
      percent: val.percent || 0,
    }))
    distChart.setOption({
      title: selectedExam.value
        ? {
            text: selectedExam.value,
            left: 'center',
            top: 6,
            textStyle: { fontSize: 13, color: '#4b5563', fontWeight: 500 },
          }
        : undefined,
      tooltip: {
        trigger: 'item',
        formatter: (p) => `${p.name}<br/>人数：${p.value} 人<br/>占比：${p.percent}%`,
      },
      series: [
        {
          type: 'pie',
          radius: ['40%', '70%'],
          center: ['50%', '50%'],
          data: distData,
          color: ['#10b981', '#2563eb', '#f59e0b', '#ef4444'],
          label: {
            color: '#4b5563',
            fontSize: 12,
            formatter: '{b}\n{d}%（{c}人）',
          },
          itemStyle: { borderColor: '#fff', borderWidth: 2 },
        },
      ],
    })
  }

  if (attRef.value) {
    if (attChart) attChart.dispose()
    attChart = echarts.init(attRef.value)
    const att = data.value.attendance || {}
    attChart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: (p) => `${p[0].axisValue}<br/>出勤率：${p[0].value}%`,
      },
      grid: { left: 40, right: 20, top: 20, bottom: 30 },
      xAxis: {
        type: 'category',
        data: (att.trend || []).map((t) => t.date),
        axisLine: { lineStyle: { color: '#e5e7eb' } },
        axisTick: { show: false },
        axisLabel: { color: '#9ca3af', fontSize: 11 },
      },
      yAxis: {
        type: 'value',
        max: 100,
        splitLine: { lineStyle: { color: '#f3f4f6' } },
        axisLabel: { color: '#9ca3af', fontSize: 11, formatter: '{value}%' },
      },
      series: [
        {
          type: 'line',
          smooth: true,
          data: (att.trend || []).map((t) => t.rate),
          areaStyle: { color: 'rgba(16,185,129,0.15)' },
          lineStyle: { color: '#10b981', width: 2 },
          itemStyle: { color: '#10b981' },
          symbol: 'circle',
          symbolSize: 6,
        },
      ],
    })
  }
}
</script>

<style scoped>
.identity-bar {
  margin-bottom: 12px;
}
.stat-row {
  margin-bottom: 16px;
}
.stat-card {
  background: #fff;
  border-radius: var(--radius-lg);
  padding: 18px 16px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: var(--shadow-card);
  transition: all var(--transition-fast);
  cursor: pointer;
  margin-bottom: 16px;
}
.stat-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}
.stat-icon-box {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-icon {
  font-size: 22px;
  color: #fff;
}
.stat-info {
  min-width: 0;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}
.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.chart-card {
  margin-bottom: 16px;
}
.chart-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  gap: 12px;
  flex-wrap: wrap;
}
.chart-head .card-title {
  margin: 0;
}
.att-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.att-rate {
  font-size: 22px;
  font-weight: 700;
  color: #10b981;
}
.alert-group {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 8px;
}
.alert-block {
  padding: 12px 14px;
  background: #fafafa;
  border-radius: var(--radius-md);
}
.alert-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}
.alert-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}
.alert-count {
  margin-left: auto;
  font-size: 12px;
  color: #fff;
  background: #dc2626;
  border-radius: 10px;
  padding: 0 8px;
  line-height: 18px;
}
.alert-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
