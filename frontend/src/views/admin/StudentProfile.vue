<template>
  <div>
    <el-page-header
      :content="profile?.student?.name || '学生画像'"
      @back="$router.back()"
      style="margin-bottom: 16px"
    />

    <!-- 首屏骨架屏 / 加载失败重试；二者都不成立时才展示画像正文 -->
    <StateView
      v-if="loading || error"
      :loading="loading"
      :error="error"
      error-description="学生画像加载失败"
      @retry="load"
    >
      <template #skeleton>
        <el-skeleton :rows="8" animated />
      </template>
    </StateView>

    <template v-else-if="profile">
      <!-- 基本信息 -->
      <div class="page-card">
        <div style="display: flex; align-items: center; gap: 16px">
          <el-avatar
            :size="56"
            style="
              background: linear-gradient(135deg, #2563eb, #4f46e5);
              font-size: 22px;
              font-weight: 700;
            "
          >
            {{ profile.student.name?.[0] }}
          </el-avatar>
          <div style="flex: 1">
            <div style="font-size: 18px; font-weight: 600">{{ profile.student.name }}</div>
            <div style="color: var(--text-tertiary); font-size: 13px; margin-top: 2px">
              学号：{{ profile.student.student_no }} ｜ 班级：{{ profile.student.class_name }} ｜
              {{ profile.student.gender }}
            </div>
          </div>
          <el-tag :type="profile.student.student_type === 'day' ? 'info' : 'warning'" size="large">
            {{ profile.student.student_type === 'day' ? '通学生' : '寄宿生' }}
          </el-tag>
        </div>
      </div>

      <!-- 寄宿/通学状态动态展示 -->
      <div class="page-card">
        <h3 class="card-title">住宿状态（寄宿/通学）</h3>
        <div class="board-current" v-if="boardCurrent">
          <span class="board-current-label">当前状态</span>
          <el-tag :type="boardCurrent.type === 'day' ? 'info' : 'warning'" size="large">{{
            boardCurrent.label
          }}</el-tag>
          <span class="board-current-since">自 {{ boardCurrent.since }} 起</span>
        </div>

        <!-- 各时间段（含起始/结束时间） -->
        <el-table v-if="boardPeriods.length" :data="boardPeriods" size="small" style="width: 100%">
          <el-table-column label="住宿类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="row.type === 'day' ? 'info' : 'warning'">{{
                row.label
              }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="起始时间" min-width="160">
            <template #default="{ row }">{{ row.start || '—' }}</template>
          </el-table-column>
          <el-table-column label="结束时间" min-width="160">
            <template #default="{ row }">
              <span
                :style="{ color: row.end ? '#374151' : '#2563eb', fontWeight: row.end ? 400 : 600 }"
              >
                {{ row.end || '至今' }}
              </span>
            </template>
          </el-table-column>
        </el-table>

        <!-- 状态变更记录 -->
        <template v-if="boardHistory.length">
          <div class="board-section-title">状态变更记录</div>
          <el-timeline>
            <el-timeline-item
              v-for="h in boardHistory"
              :key="h.id"
              :timestamp="h.changed_at || h.created_at"
            >
              <el-tag :type="h.old_type === 'day' ? 'info' : 'warning'" size="small">{{
                h.old_label
              }}</el-tag>
              <el-icon style="margin: 0 6px; vertical-align: middle"><Right /></el-icon>
              <el-tag :type="h.new_type === 'day' ? 'info' : 'warning'" size="small">{{
                h.new_label
              }}</el-tag>
              <span
                v-if="h.changed_by_name"
                style="color: #9ca3af; font-size: 12px; margin-left: 8px"
                >操作人：{{ h.changed_by_name }}</span
              >
            </el-timeline-item>
          </el-timeline>
        </template>
        <div v-else-if="!boardPeriods.length" class="empty-state">暂无住宿状态记录</div>
      </div>

      <!-- 雷达图 -->
      <div class="page-card">
        <h3 class="card-title">综合评价雷达</h3>
        <div ref="radarRef" style="width: 100%; height: 340px"></div>

        <!-- 各维度评价依据说明 -->
        <div class="radar-basis">
          <div class="basis-title">各维度评分依据说明</div>
          <div class="basis-grid">
            <div class="basis-item" v-for="d in radarBasis" :key="d.key">
              <div class="basis-item-head">
                <span class="basis-name">{{ d.name }}</span>
                <span class="basis-score">{{ d.score }} 分</span>
              </div>
              <div class="basis-row">
                <span class="basis-label">数据来源</span>
                <span class="basis-text">{{ d.source }}</span>
              </div>
              <div class="basis-row">
                <span class="basis-label">计算方法</span>
                <span class="basis-text">{{ d.method }}</span>
              </div>
              <div class="basis-row">
                <span class="basis-label">相关指标</span>
                <div class="basis-indicators">
                  <el-tag
                    v-for="(t, i) in d.indicators"
                    :key="i"
                    size="small"
                    effect="plain"
                    type="info"
                    >{{ t }}</el-tag
                  >
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 数据概览 -->
      <div class="page-card">
        <h3 class="card-title">数据概览</h3>
        <el-row :gutter="12">
          <el-col :span="12" v-for="s in summaryCards" :key="s.label">
            <div class="stat-mini">
              <div class="stat-mini-value" :style="{ color: s.color }">{{ s.value }}</div>
              <div class="stat-mini-label">{{ s.label }}</div>
            </div>
          </el-col>
        </el-row>
      </div>

      <!-- 成绩趋势 -->
      <div class="page-card">
        <h3 class="card-title">成绩趋势</h3>
        <div v-if="hasTrend" ref="trendRef" style="width: 100%; height: 280px"></div>
        <div v-else class="empty-state">暂无成绩记录</div>
      </div>

      <!-- 个性化标签 -->
      <div class="page-card">
        <div
          style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
          "
        >
          <h3 class="card-title" style="margin: 0">个性化标签</h3>
          <el-button size="small" type="primary" @click="openTagDialog">添加标签</el-button>
        </div>
        <div v-if="profile.tags.length" style="display: flex; flex-wrap: wrap; gap: 8px">
          <el-tag
            v-for="t in profile.tags"
            :key="t.id"
            closable
            :type="tagType(t.category)"
            @close="removeTag(t)"
            >{{ t.tag }}</el-tag
          >
        </div>
        <div v-else class="empty-state" style="padding: 24px 0">暂无标签</div>
      </div>

      <!-- 积分历程 -->
      <div class="page-card">
        <h3 class="card-title">积分历程</h3>
        <el-timeline v-if="profile.point_summary.timeline.length">
          <el-timeline-item
            v-for="(p, i) in profile.point_summary.timeline"
            :key="i"
            :timestamp="p.date"
            :color="p.points >= 0 ? '#10b981' : '#ef4444'"
          >
            <span :style="{ color: p.points >= 0 ? '#10b981' : '#ef4444', fontWeight: 600 }"
              >{{ p.points >= 0 ? '+' : '' }}{{ p.points }}</span
            >
            {{ p.reason }}
          </el-timeline-item>
        </el-timeline>
        <div v-else class="empty-state">暂无积分记录</div>
      </div>

      <!-- 近期表现 -->
      <div class="page-card">
        <h3 class="card-title">近期表现</h3>
        <el-timeline v-if="profile.performance_summary.recent.length">
          <el-timeline-item
            v-for="(p, i) in profile.performance_summary.recent"
            :key="i"
            :timestamp="p.date"
            :color="p.ptype === '积极' ? '#10b981' : '#ef4444'"
          >
            <el-tag :type="p.ptype === '积极' ? 'success' : 'danger'" size="small" effect="plain">{{
              p.ptype
            }}</el-tag>
            {{ p.content }}
          </el-timeline-item>
        </el-timeline>
        <div v-else class="empty-state">暂无表现记录</div>
      </div>
    </template>
  </div>

  <!-- 添加标签 -->
  <el-dialog v-model="tagDialog" title="添加标签" width="380px">
    <el-form label-width="70px">
      <el-form-item label="标签内容" required
        ><el-input v-model="tagForm.tag" placeholder="如：编程能手" maxlength="20"
      /></el-form-item>
      <el-form-item label="分类">
        <el-select v-model="tagForm.category" style="width: 100%">
          <el-option label="学业" value="学业" /><el-option label="品德" value="品德" />
          <el-option label="技能" value="技能" /><el-option label="特长" value="特长" />
          <el-option label="自定义" value="自定义" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="tagDialog = false">取消</el-button>
      <el-button type="primary" :loading="tagSaving" @click="addTag">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts/core'
import { LineChart, RadarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, RadarComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([
  LineChart,
  RadarChart,
  GridComponent,
  TooltipComponent,
  RadarComponent,
  CanvasRenderer,
])
import { studentApi } from '../../api'
import StateView from '../../components/StateView.vue'

const route = useRoute()
const profile = ref(null)
const loading = ref(true)
const error = ref(false)
const boardHistory = ref([])
const boardCurrent = ref(null)
const boardPeriods = ref([])
const radarRef = ref(null)
const trendRef = ref(null)
let radarChart = null
let trendChart = null

const tagDialog = ref(false)
const tagSaving = ref(false)
const tagForm = reactive({ tag: '', category: '自定义' })

const hasTrend = computed(() => profile.value?.score_summary?.trend?.length > 0)

const radarBasis = computed(() => profile.value?.radar_basis || [])

const summaryCards = computed(() => {
  if (!profile.value) return []
  const p = profile.value
  return [
    { label: '成绩均分', value: p.score_summary.avg || '—', color: '#2563eb' },
    {
      label: '积分总计',
      value: p.point_summary.total,
      color: p.point_summary.total >= 0 ? '#10b981' : '#ef4444',
    },
    {
      label: '出勤率',
      value: `${Math.max(0, 100 - p.leave_summary.total * 5)}%`,
      color: '#8b5cf6',
    },
    {
      label: '优秀作品',
      value: `${p.submission_summary.excellent}/${p.submission_summary.total}`,
      color: '#f59e0b',
    },
    { label: '积极表现', value: p.performance_summary.positive, color: '#10b981' },
    { label: '消极表现', value: p.performance_summary.negative, color: '#ef4444' },
  ]
})

function tagType(cat) {
  const map = { 学业: 'primary', 品德: 'success', 技能: 'warning', 特长: 'danger' }
  return map[cat] || 'info'
}

onMounted(load)

async function load() {
  loading.value = true
  error.value = false
  try {
    profile.value = await studentApi.profile(route.params.id)
    const h = await studentApi.boardHistory(route.params.id)
    boardHistory.value = h.items || []
    boardCurrent.value = h.current || null
    boardPeriods.value = h.periods || []
  } catch (e) {
    error.value = true
  } finally {
    loading.value = false
  }
  await nextTick()
  setTimeout(() => renderCharts(), 0)
}

onBeforeUnmount(() => {
  if (radarChart) {
    radarChart.dispose()
    radarChart = null
  }
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
})

function renderCharts() {
  if (radarRef.value && profile.value) {
    if (radarChart) radarChart.dispose()
    radarChart = echarts.init(radarRef.value)
    const r = profile.value.radar
    radarChart.setOption({
      tooltip: {
        formatter: (params) => {
          const p = profile.value
          const dims = [
            {
              name: '学业',
              val: r.academic,
              basis: `数据来源：${p.score_summary.total} 次考试成绩\n计算方法：成绩均分 = ${p.score_summary.avg} 分\n指标：最高 ${p.score_summary.max} / 最低 ${p.score_summary.min}`,
            },
            {
              name: '品德',
              val: r.moral,
              basis: `数据来源：${p.point_summary.count} 条积分记录\n计算方法：50 + 积分总计(${p.point_summary.total}) × 2\n指标：正分 ${p.point_summary.positive} / 负分 ${p.point_summary.negative}`,
            },
            {
              name: '出勤',
              val: r.attendance,
              basis: `数据来源：${p.leave_summary.total} 次请假记录\n计算方法：100 - 请假次数(${p.leave_summary.total}) × 5`,
            },
            {
              name: '技能',
              val: r.skill,
              basis: `数据来源：${p.submission_summary.total} 次作业提交\n计算方法：优秀率 = ${p.submission_summary.rate}%\n指标：优秀 ${p.submission_summary.excellent} / 总提交 ${p.submission_summary.total}`,
            },
          ]
          const d = dims.find((d) => d.name === params.name)
          return d
            ? `<b>${d.name}</b>：${d.val} 分<br/><br/>${d.basis.replace(/\n/g, '<br/>')}`
            : ''
        },
      },
      radar: {
        center: ['50%', '50%'],
        radius: '65%',
        indicator: [
          { name: '学业', max: 100 },
          { name: '品德', max: 100 },
          { name: '出勤', max: 100 },
          { name: '技能', max: 100 },
        ],
        axisName: { color: '#4b5563', fontSize: 12 },
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              value: [r.academic, r.moral, r.attendance, r.skill],
              name: '综合评分',
              areaStyle: { color: 'rgba(37,99,235,0.15)' },
            },
          ],
          lineStyle: { color: '#2563eb', width: 2 },
          itemStyle: { color: '#2563eb' },
          symbol: 'circle',
          symbolSize: 5,
        },
      ],
    })
  }

  if (trendRef.value && hasTrend.value) {
    if (trendChart) trendChart.dispose()
    trendChart = echarts.init(trendRef.value)
    const trend = profile.value.score_summary.trend
    trendChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 20, top: 20, bottom: 30 },
      xAxis: {
        type: 'category',
        data: trend.map((t) => t.date),
        axisLabel: { color: '#9ca3af', fontSize: 11, rotate: 30 },
      },
      yAxis: {
        type: 'value',
        min: 0,
        max: 100,
        splitLine: { lineStyle: { color: '#f3f4f6' } },
        axisLabel: { color: '#9ca3af', fontSize: 11 },
      },
      series: [
        {
          type: 'line',
          smooth: true,
          data: trend.map((t) => t.score),
          areaStyle: { color: 'rgba(37,99,235,0.15)' },
          lineStyle: { color: '#2563eb', width: 2 },
          itemStyle: { color: '#2563eb' },
          symbol: 'circle',
          symbolSize: 6,
        },
      ],
    })
  }
}

function openTagDialog() {
  tagForm.tag = ''
  tagForm.category = '自定义'
  tagDialog.value = true
}

async function addTag() {
  if (!tagForm.tag.trim()) return ElMessage.warning('请输入标签内容')
  tagSaving.value = true
  try {
    await studentApi.addTag(route.params.id, {
      tag: tagForm.tag.trim(),
      category: tagForm.category,
    })
    ElMessage.success('标签添加成功')
    tagDialog.value = false
    profile.value = await studentApi.profile(route.params.id)
  } catch (e) {
    console.error('[StudentProfile] 添加标签失败:', e)
  } finally {
    tagSaving.value = false
  }
}

async function removeTag(tag) {
  try {
    await studentApi.removeTag(route.params.id, tag.id)
    ElMessage.success('标签已移除')
    profile.value = await studentApi.profile(route.params.id)
  } catch (e) {
    console.error('[StudentProfile] 移除标签失败:', e)
  }
}
</script>

<style scoped>
.stat-mini {
  padding: 12px;
  border-radius: var(--radius-md);
  background: #f8fafc;
  margin-bottom: 12px;
  text-align: center;
}
.stat-mini-value {
  font-size: 22px;
  font-weight: 700;
}
.stat-mini-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

/* 雷达图评价依据 */
.radar-basis {
  margin-top: 16px;
  border-top: 1px solid #eef1f6;
  padding-top: 16px;
}
.basis-title {
  font-weight: 600;
  font-size: 14px;
  color: #111827;
  margin-bottom: 12px;
}
.basis-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.basis-item {
  background: #f8fafc;
  border-radius: 10px;
  padding: 12px 14px;
}
.basis-item-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.basis-name {
  font-weight: 600;
  color: #2563eb;
  font-size: 14px;
}
.basis-score {
  font-weight: 700;
  color: #2563eb;
  font-size: 13px;
}
.basis-row {
  display: flex;
  margin-bottom: 6px;
  font-size: 13px;
  color: #374151;
  line-height: 1.6;
}
.basis-row:last-child {
  margin-bottom: 0;
}
.basis-label {
  flex-shrink: 0;
  width: 60px;
  color: #9ca3af;
  font-size: 12px;
  padding-top: 1px;
}
.basis-text {
  flex: 1;
}
.basis-indicators {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
@media (max-width: 900px) {
  .basis-grid {
    grid-template-columns: 1fr;
  }
}

/* 住宿状态动态展示 */
.board-current {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #eff6ff, #f5f3ff);
  border-radius: 10px;
  margin-bottom: 14px;
}
.board-current-label {
  color: #6b7280;
  font-size: 13px;
}
.board-current-since {
  color: #6b7280;
  font-size: 13px;
  margin-left: 4px;
}
.board-section-title {
  font-weight: 600;
  font-size: 14px;
  color: #111827;
  margin: 16px 0 10px;
}
</style>
