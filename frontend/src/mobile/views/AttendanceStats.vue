<template>
  <div class="m-stats">
    <van-dropdown-menu>
      <van-dropdown-item v-model="classId" :options="classOptions" @change="load" />
    </van-dropdown-menu>

    <van-tabs v-model:active="range" @change="load" style="margin-top: 4px">
      <van-tab title="近 7 天" name="7" />
      <van-tab title="近 30 天" name="30" />
    </van-tabs>

    <div v-if="summary" class="m-body">
      <!-- 出勤率 -->
      <div class="m-rate-card">
        <van-circle
          :current-rate="summary.attendance_rate"
          :rate="summary.attendance_rate"
          :size="140"
          :stroke-width="60"
          color="#2563eb"
          layer-color="#eef2ff"
          :text="`${summary.attendance_rate}%`"
        />
        <div class="m-rate-label">
          <div>出勤率</div>
          <div class="m-rate-sub">
            在籍 {{ summary.student_count }} 人 · 记录 {{ summary.total }} 人次
          </div>
        </div>
      </div>

      <!-- 状态分布 -->
      <div class="m-grid">
        <div class="m-grid-item" v-for="s in statusList" :key="s.name">
          <div class="m-num" :style="{ color: s.color }">{{ summary.status_count[s.name] }}</div>
          <div class="m-label">{{ s.name }}</div>
        </div>
      </div>

      <!-- 逐日趋势 -->
      <van-cell-group inset title="逐日趋势">
        <van-cell
          v-for="t in summary.trend"
          :key="t.date"
          :title="t.date"
          :label="`出勤 ${t['出勤']} · 缺勤 ${t['缺勤']} · 请假 ${t['请假']} · 迟到 ${t['迟到']}`"
        >
          <template #value>
            <span :style="{ color: rateColor(t.rate) }">{{ t.rate }}%</span>
          </template>
        </van-cell>
        <van-cell v-if="!summary.trend.length" title="暂无考勤数据" />
      </van-cell-group>
    </div>
    <van-empty v-else-if="!loading" description="请先选择班级" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { attendanceApi } from '../../api'
import { formatDate } from '../../utils/date'
import { useClassOptions } from '../composables/useClassOptions'

const { classId, classOptions, loadClasses } = useClassOptions(load)
const range = ref('7')
const summary = ref(null)
const loading = ref(false)

const statusList = [
  { name: '出勤', color: '#16a34a' },
  { name: '缺勤', color: '#dc2626' },
  { name: '请假', color: '#f59e0b' },
  { name: '迟到', color: '#2563eb' },
]

function rangeDates() {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - (Number(range.value) - 1))
  return { start_date: formatDate(start), end_date: formatDate(end) }
}

function rateColor(rate) {
  if (rate >= 95) return '#16a34a'
  if (rate >= 85) return '#f59e0b'
  return '#dc2626'
}

// 竞态守卫：班级/区间切换并发在途时，旧响应晚到不覆盖新数据
let loadSeq = 0

async function load() {
  if (!classId.value) return
  const seq = ++loadSeq
  loading.value = true
  try {
    const { start_date, end_date } = rangeDates()
    const res = await attendanceApi.summary({ class_id: classId.value, start_date, end_date })
    if (seq !== loadSeq) return
    summary.value = res
  } catch (e) {
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

onMounted(loadClasses)
</script>

<style scoped>
.m-stats {
  padding-bottom: 20px;
}
.m-body {
  padding: 16px;
}
.m-rate-card {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 12px;
}
.m-rate-label {
  font-size: 15px;
  font-weight: 600;
}
.m-rate-sub {
  font-size: 12px;
  font-weight: 400;
  color: #6b7280;
  margin-top: 4px;
}
.m-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}
.m-grid-item {
  background: #fff;
  border-radius: 10px;
  padding: 14px 0;
  text-align: center;
}
.m-num {
  font-size: 22px;
  font-weight: 700;
}
.m-label {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}
</style>
