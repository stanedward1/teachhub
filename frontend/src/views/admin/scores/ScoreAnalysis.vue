<template>
  <div>
    <div class="toolbar">
      <StudentSelect
        v-model="analysisClassId"
        show-class-filter
        placeholder="选择班级"
        style="width: 280px"
        @update:model-value="loadAnalysis"
      />
      <el-select
        v-model="analysisSubject"
        placeholder="全部科目"
        clearable
        filterable
        style="width: 160px"
        @change="loadAnalysis"
      >
        <el-option v-for="s in analysisSubjects" :key="s" :label="s" :value="s" />
      </el-select>
      <el-select
        v-model="analysisExam"
        placeholder="全部考试"
        clearable
        filterable
        style="width: 180px"
        @change="loadAnalysis"
      >
        <el-option v-for="e in analysisExams" :key="e" :label="e" :value="e" />
      </el-select>
      <el-button @click="loadAnalysis">查询</el-button>
    </div>

    <div class="page-card">
      <div class="analysis-head">
        <h3 class="card-title" style="margin: 0">班级成绩排名</h3>
        <span v-if="ranking.length" style="color: var(--text-tertiary); font-size: 13px"
          >共 {{ ranking.length }} 人（按{{ analysisSubject || '全部科目' }}均分排名）</span
        >
      </div>
      <StateView
        :loading="analysisLoading"
        :error="analysisError"
        :empty="!ranking.length"
        :columns="6"
        empty-description="该班级暂无成绩，请先在成绩列表录入"
        @retry="loadAnalysis"
      >
        <el-table :data="ranking" v-loading="analysisLoading" style="width: 100%">
          <el-table-column label="名次" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.rank <= 3 ? 'warning' : 'info'" size="small" effect="light">{{
                row.rank
              }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="学生" width="140" />
          <el-table-column prop="student_no" label="学号" width="120" />
          <el-table-column prop="score" label="均分" width="100">
            <template #default="{ row }">
              <span style="font-weight: 600; color: #2563eb">{{ row.score }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="count" label="记录数" width="100" />
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="viewTrend(row)">查看趋势</el-button>
            </template>
          </el-table-column>
        </el-table>
      </StateView>
    </div>

    <!-- 学生成绩趋势弹窗 -->
    <el-dialog v-model="trendDialog" :title="`${trendName} 的成绩趋势`" width="760px">
      <div ref="trendChartRef" style="width: 100%; height: 360px"></div>
      <div v-if="!trendData.length" class="empty-state">该学生暂无成绩记录</div>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * 成绩分析页签。
 *
 * 从 Scores.vue 原样搬迁而来（模板 46-87 行的页签内部内容 + 趋势弹窗 91-94 行，
 * 以及全部 analysis / trend 状态与函数、`.analysis-head` 样式）。
 * 通过 props.active 监听页签切入，等价替代原父组件的 `@tab-change` 触发
 * loadAnalysisOptions（不加 immediate，保证首屏不产生额外请求）。
 */
import { ref, watch, nextTick } from 'vue'
import StudentSelect from '../../../components/StudentSelect.vue'
import StateView from '../../../components/StateView.vue'
import { scoreApi } from '../../../api'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps({
  /** 当前页签是否为「成绩分析」 */
  active: { type: Boolean, default: false },
})

// 成绩分析
const analysisClassId = ref(null)
const analysisSubject = ref('')
const analysisExam = ref('')
const analysisSubjects = ref([])
const analysisExams = ref([])
const ranking = ref([])
const analysisLoading = ref(false)
const analysisError = ref(false)

// 趋势弹窗
const trendDialog = ref(false)
const trendName = ref('')
const trendData = ref([])
const trendChartRef = ref(null)
let trendChart = null

// 由父组件页签切换驱动（原为父组件的 onTabChange）
watch(
  () => props.active,
  (v) => {
    if (v) loadAnalysisOptions()
  }
)

async function loadAnalysisOptions() {
  // 拉取可选科目/考试（不指定班级时返回当前教师可见范围内的全部）
  try {
    const res = await scoreApi.analysis({})
    analysisSubjects.value = res.subjects || []
    analysisExams.value = res.exams || []
  } catch (e) {}
}

async function loadAnalysis() {
  if (!analysisClassId.value) return
  analysisLoading.value = true
  analysisError.value = false
  try {
    const res = await scoreApi.analysis({
      class_id: analysisClassId.value,
      subject: analysisSubject.value || '',
      exam_name: analysisExam.value || '',
    })
    ranking.value = res.ranking || []
    analysisSubjects.value = res.subjects || analysisSubjects.value
    analysisExams.value = res.exams || analysisExams.value
  } catch (e) {
    analysisError.value = true
  } finally {
    analysisLoading.value = false
  }
}

async function viewTrend(row) {
  trendName.value = row.name
  trendDialog.value = true
  try {
    const res = await scoreApi.analysis({ student_id: row.student_id })
    trendData.value = res.trend || []
    await nextTick()
    renderTrendChart()
  } catch (e) {}
}

function renderTrendChart() {
  if (!trendChartRef.value || !trendData.value.length) return
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
  trendChart = echarts.init(trendChartRef.value)
  // 按科目分组，绘制多条折线（含班级均分对比虚线）
  const bySubject = {}
  for (const t of trendData.value) {
    bySubject[t.subject] = bySubject[t.subject] || { dates: [], scores: [], avgs: [] }
    bySubject[t.subject].dates.push(t.exam || t.date)
    bySubject[t.subject].scores.push(t.score)
    bySubject[t.subject].avgs.push(t.class_avg ?? null)
  }
  const series = []
  const legendData = []
  for (const [subj, d] of Object.entries(bySubject)) {
    legendData.push(subj)
    series.push({
      name: subj,
      type: 'line',
      smooth: true,
      data: d.scores,
      lineStyle: { width: 2 },
      itemStyle: { color: colorFor(subj) },
      symbol: 'circle',
      symbolSize: 6,
    })
    if (d.avgs.some((v) => v != null)) {
      legendData.push(`${subj}·班级均分`)
      series.push({
        name: `${subj}·班级均分`,
        type: 'line',
        data: d.avgs,
        lineStyle: { type: 'dashed', width: 1.5, color: colorFor(subj) },
        itemStyle: { color: colorFor(subj) },
        symbol: 'none',
      })
    }
  }
  // 横轴取第一个科目的时间轴（各科目考试时间可能不同，这里简化）
  const firstKey = Object.keys(bySubject)[0]
  const xData = firstKey ? bySubject[firstKey].dates : []
  trendChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: legendData, bottom: 0, textStyle: { color: '#6b7280', fontSize: 12 } },
    grid: { left: 40, right: 24, top: 30, bottom: 60 },
    xAxis: {
      type: 'category',
      data: xData,
      axisLabel: { color: '#9ca3af', fontSize: 11, rotate: 20 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: '#f3f4f6' } },
      axisLabel: { color: '#9ca3af', fontSize: 11 },
    },
    series,
  })
}

const COLOR_PALETTE = [
  '#2563eb',
  '#10b981',
  '#f59e0b',
  '#8b5cf6',
  '#ef4444',
  '#06b6d4',
  '#ec4899',
  '#84cc16',
]
function colorFor(subj) {
  let h = 0
  for (let i = 0; i < subj.length; i++) h = (h * 31 + subj.charCodeAt(i)) % 997
  return COLOR_PALETTE[h % COLOR_PALETTE.length]
}
</script>

<style scoped>
.analysis-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
</style>
