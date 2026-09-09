<template>
  <el-drawer
    :model-value="visible"
    :title="profile ? profile.student.name : '学生卡片'"
    size="480px"
    direction="rtl"
    @update:model-value="onClose"
  >
    <div v-if="loading" style="text-align: center; padding: 60px 0; color: #9ca3af;">
      <el-icon class="is-loading" style="font-size: 28px;"><Loading /></el-icon>
      <p style="margin-top: 12px;">加载中...</p>
    </div>

    <div v-else-if="profile" class="student-card">
      <!-- 基本信息 -->
      <div class="sc-header">
        <el-avatar :size="52" style="background: linear-gradient(135deg, #2563eb, #4f46e5); font-weight: 700;">
          {{ profile.student.name?.[0] }}
        </el-avatar>
        <div style="flex: 1; min-width: 0;">
          <div style="font-size: 16px; font-weight: 600;">{{ profile.student.name }}</div>
          <div style="color: var(--text-tertiary); font-size: 12px; margin-top: 2px;">
            {{ profile.student.student_no }} ｜ {{ profile.student.class_name }}
          </div>
        </div>
        <el-tag :type="profile.student.student_type === 'day' ? 'info' : 'warning'" size="small">
          {{ profile.student.student_type === 'day' ? '通学生' : '寄宿生' }}
        </el-tag>
      </div>

      <!-- 四维雷达 -->
      <div class="sc-radar">
        <div ref="radarRef" style="width: 100%; height: 220px;"></div>
      </div>

      <!-- 关键指标 -->
      <div class="sc-stats">
        <div class="sc-stat">
          <div class="sc-stat-val" style="color: #2563eb;">{{ profile.score_summary.avg || '—' }}</div>
          <div class="sc-stat-label">成绩均分</div>
        </div>
        <div class="sc-stat">
          <div class="sc-stat-val" :style="{ color: profile.point_summary.total >= 0 ? '#10b981' : '#ef4444' }">{{ profile.point_summary.total }}</div>
          <div class="sc-stat-label">积分总计</div>
        </div>
        <div class="sc-stat">
          <div class="sc-stat-val" style="color: #8b5cf6;">{{ Math.max(0, 100 - profile.leave_summary.total * 5) }}%</div>
          <div class="sc-stat-label">出勤率</div>
        </div>
        <div class="sc-stat">
          <div class="sc-stat-val" style="color: #f59e0b;">{{ profile.performance_summary.positive }}/{{ profile.performance_summary.negative }}</div>
          <div class="sc-stat-label">积极/消极</div>
        </div>
      </div>

      <!-- 标签 -->
      <div class="sc-section" v-if="profile.tags?.length">
        <div class="sc-section-title">个性化标签</div>
        <div style="display: flex; flex-wrap: wrap; gap: 6px;">
          <el-tag v-for="t in profile.tags" :key="t.id" size="small" effect="plain">{{ t.tag }}</el-tag>
        </div>
      </div>

      <!-- 近期表现 -->
      <div class="sc-section" v-if="profile.performance_summary.recent?.length">
        <div class="sc-section-title">近期表现</div>
        <div class="sc-timeline">
          <div v-for="(p, i) in profile.performance_summary.recent.slice(0, 5)" :key="i" class="sc-timeline-item">
            <el-tag :type="p.ptype === '积极' ? 'success' : 'danger'" size="small" effect="plain">{{ p.ptype }}</el-tag>
            <span class="sc-timeline-content">{{ p.content }}</span>
            <span class="sc-timeline-date">{{ p.date }}</span>
          </div>
        </div>
      </div>

      <!-- 近期请假 -->
      <div class="sc-section" v-if="profile.leave_summary.recent?.length">
        <div class="sc-section-title">近期请假</div>
        <div class="sc-timeline">
          <div v-for="(l, i) in profile.leave_summary.recent.slice(0, 5)" :key="i" class="sc-timeline-item">
            <span class="sc-timeline-content">{{ l.reason }}</span>
            <span class="sc-timeline-date">{{ l.start }} ~ {{ l.end }}</span>
          </div>
        </div>
      </div>

      <!-- 操作 -->
      <div class="sc-footer">
        <el-button v-if="profile.student.parent_phone" link type="primary" @click="callParent">
          <el-icon style="margin-right: 4px;"><Phone /></el-icon>联系家长 {{ profile.student.parent_phone }}
        </el-button>
        <div class="spacer"></div>
        <el-button type="primary" @click="goProfile">查看完整画像</el-button>
      </div>
    </div>

    <div v-else style="text-align: center; padding: 60px 0; color: #9ca3af;">暂无学生信息</div>
  </el-drawer>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { studentApi } from '../api'
import * as echarts from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { RadarComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([RadarChart, RadarComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  visible: { type: Boolean, default: false },
  studentId: { type: [Number, String], default: null }
})
const emit = defineEmits(['update:visible'])

const router = useRouter()
const profile = ref(null)
const loading = ref(false)
const radarRef = ref(null)
let radarChart = null

watch(
  () => [props.visible, props.studentId],
  async ([vis, id]) => {
    if (vis && id) {
      await load(id)
    }
  },
  { immediate: true }
)

async function load(id) {
  loading.value = true
  profile.value = null
  try {
    profile.value = await studentApi.profile(id)
    await nextTick()
    renderRadar()
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function renderRadar() {
  if (!radarRef.value || !profile.value) return
  if (radarChart) { radarChart.dispose(); radarChart = null }
  radarChart = echarts.init(radarRef.value)
  const r = profile.value.radar
  radarChart.setOption({
    tooltip: {},
    radar: {
      center: ['50%', '50%'],
      radius: '65%',
      indicator: [
        { name: '学业', max: 100 },
        { name: '品德', max: 100 },
        { name: '出勤', max: 100 },
        { name: '技能', max: 100 },
      ],
      axisName: { color: '#6b7280', fontSize: 11 }
    },
    series: [{
      type: 'radar',
      data: [{ value: [r.academic, r.moral, r.attendance, r.skill], name: '综合评分', areaStyle: { color: 'rgba(37,99,235,0.12)' } }],
      lineStyle: { color: '#2563eb', width: 2 },
      itemStyle: { color: '#2563eb' },
      symbol: 'circle',
      symbolSize: 4,
    }]
  })
}

function onClose(v) {
  emit('update:visible', v)
}

function goProfile() {
  if (profile.value?.student?.id) {
    onClose(false)
    router.push(`/admin/students/${profile.value.student.id}/profile`)
  }
}

function callParent() {
  const phone = profile.value?.student?.parent_phone
  if (phone) window.location.href = `tel:${phone}`
}
</script>

<style scoped>
.student-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sc-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.sc-radar {
  background: #f8fafc;
  border-radius: var(--radius-md);
  padding: 8px;
}
.sc-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.sc-stat {
  background: #f8fafc;
  border-radius: var(--radius-md);
  padding: 12px;
  text-align: center;
}
.sc-stat-val {
  font-size: 20px;
  font-weight: 700;
}
.sc-stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.sc-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
  margin-bottom: 8px;
}
.sc-timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sc-timeline-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: #374151;
  line-height: 1.5;
}
.sc-timeline-content {
  flex: 1;
}
.sc-timeline-date {
  flex-shrink: 0;
  color: #9ca3af;
  font-size: 12px;
}
.sc-footer {
  display: flex;
  align-items: center;
  border-top: 1px solid var(--border-light);
  padding-top: 12px;
}
.spacer { flex: 1; }
</style>
