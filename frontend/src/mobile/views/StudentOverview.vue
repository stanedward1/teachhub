<template>
  <div class="m-overview" v-if="data">
    <!-- 基本信息 -->
    <div class="m-basic">
      <div class="m-stu-avatar">{{ data.student?.name?.[0] }}</div>
      <div class="m-basic-info">
        <div class="m-name">{{ data.student?.name }}</div>
        <div class="m-meta">{{ data.student?.student_no }} · {{ data.student?.class_name }}</div>
        <van-tag
          :type="data.student?.student_type === 'day' ? 'primary' : 'warning'"
          plain
          size="small"
          style="margin-top: 4px"
        >
          {{ data.student?.student_type === 'day' ? '通学生' : '寄宿生' }}
        </van-tag>
      </div>
    </div>

    <!-- 五维雷达 -->
    <div class="m-card">
      <div class="m-card-title">五维画像</div>
      <div ref="radarRef" style="width: 100%; height: 280px"></div>
    </div>

    <!-- 关键指标 -->
    <van-cell-group inset title="关键指标">
      <van-cell title="成绩平均分" :value="`${data.score_summary.avg} 分（${data.score_summary.total} 次）`" />
      <van-cell title="积分总计" :value="`${data.point_summary.total} 分`" />
      <van-cell title="积极表现" :value="`${data.performance_summary.positive} 次`" />
      <van-cell title="请假记录" :value="`${data.leave_summary.total} 次`" />
    </van-cell-group>

    <!-- 标签 -->
    <van-cell-group inset title="画像标签">
      <van-cell v-if="data.tags.length">
        <template #default>
          <van-tag v-for="t in data.tags" :key="t" type="primary" plain style="margin-right: 6px">
            {{ t }}
          </van-tag>
        </template>
      </van-cell>
      <van-cell v-else title="暂无标签" />
    </van-cell-group>

    <!-- 最近表现 -->
    <van-cell-group inset title="最近表现">
      <van-cell
        v-for="(p, i) in data.performance_summary.recent"
        :key="i"
        :title="p.content"
        :label="p.date"
      >
        <template #value>
          <van-tag :type="p.ptype === '积极' ? 'success' : 'danger'" size="small">
            {{ p.ptype }}
          </van-tag>
        </template>
      </van-cell>
      <van-cell v-if="!data.performance_summary.recent.length" title="暂无记录" />
    </van-cell-group>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, RadarComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([RadarChart, TooltipComponent, RadarComponent, CanvasRenderer])
import { mobileApi } from '../api/mobile'

const route = useRoute()
const data = ref(null)
const radarRef = ref(null)
let chart = null

async function load() {
  try {
    data.value = await mobileApi.overview(route.params.id)
    await nextTick()
    renderRadar()
  } catch (e) {
  }
}

function renderRadar() {
  if (!radarRef.value || !data.value) return
  if (chart) chart.dispose()
  chart = echarts.init(radarRef.value)
  const r = data.value.radar
  chart.setOption({
    tooltip: {},
    radar: {
      indicator: [
        { name: '学业', max: 100 },
        { name: '品德', max: 100 },
        { name: '出勤', max: 100 },
        { name: '活动', max: 100 },
        { name: '技能', max: 100 }
      ],
      radius: '65%'
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: [r.academic, r.moral, r.attendance, r.activity, r.skill],
            name: '画像',
            areaStyle: { color: 'rgba(37,99,235,0.25)' },
            lineStyle: { color: '#2563eb' },
            itemStyle: { color: '#2563eb' }
          }
        ]
      }
    ]
  })
}

onMounted(load)

onBeforeUnmount(() => {
  if (chart) { chart.dispose(); chart = null }
})
</script>

<style scoped>
.m-overview {
  padding-bottom: 12px;
}
.m-basic {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  padding: 16px;
  margin-bottom: 12px;
}
.m-stu-avatar {
  width: 52px;
  height: 52px;
  line-height: 52px;
  text-align: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  font-size: 22px;
  font-weight: 600;
}
.m-name {
  font-size: 18px;
  font-weight: 600;
}
.m-meta {
  font-size: 13px;
  color: #6b7280;
  margin-top: 2px;
}
.m-card {
  background: #fff;
  border-radius: 8px;
  padding: 12px 8px;
  margin: 0 16px 12px;
}
.m-card-title {
  font-size: 15px;
  font-weight: 600;
  padding: 4px 8px;
}
</style>
