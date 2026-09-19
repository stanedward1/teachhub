<template>
  <div class="page-card">
    <div style="font-weight: 500; margin-bottom: 12px">通学生与寄宿生人数对比</div>
    <div ref="chartRef" style="width: 100%; height: 320px"></div>
  </div>

  <!-- 通学生/寄宿生明细弹窗 -->
  <el-dialog v-model="detailDialog" :title="detailTitle" width="560px">
    <el-table :data="detailList" max-height="400" style="width: 100%">
      <el-table-column prop="student_no" label="学号" width="120" />
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column prop="gender" label="性别" width="70" />
      <el-table-column prop="class_name" label="班级" width="160" />
      <el-table-column prop="major" label="专业" min-width="140" />
    </el-table>
  </el-dialog>
</template>

<script setup>
/**
 * 通学生/寄宿生人数对比饼图（含点击扇区查看明细名单）。
 *
 * 从 Students.vue 原样搬出：echarts 按需引入、饼图 option、点击跳明细逻辑均逐字保留。
 * 取数改为本组件负责，通过 watch 监听 classId 变化（immediate）触发加载；同时对外
 * 暴露 reload()，供父组件在保存学生后主动刷新图表（等价于原 loadBoardTypeStats 调用）。
 */
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])
import { studentApi } from '../../../api'

const props = defineProps({
  /** 当前筛选班级 id（为空时不渲染本组件，由父组件 v-if 控制） */
  classId: { type: [Number, String], default: null },
})

const chartRef = ref(null)
let chartInstance = null
const detailDialog = ref(false)
const detailTitle = ref('')
const detailList = ref([])

// 加载通学生/寄宿生统计数据并渲染图表
async function load() {
  try {
    const stats = await studentApi.boardTypeStats({ class_id: props.classId })
    await nextTick()
    setTimeout(() => renderChart(stats), 0)
  } catch (e) {
    // ignore
  }
}

function renderChart(stats) {
  if (!chartRef.value) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} 人 ({d}%)',
    },
    legend: {
      bottom: 0,
    },
    series: [
      {
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: {
          show: true,
          formatter: '{b}\n{c} 人 ({d}%)',
        },
        emphasis: {
          label: { fontSize: 18, fontWeight: 'bold' },
        },
        data: [
          { value: stats.day_count, name: '通学生', itemStyle: { color: '#409EFF' } },
          { value: stats.boarding_count, name: '寄宿生', itemStyle: { color: '#E6A23C' } },
        ],
      },
    ],
  }

  chartInstance.setOption(option)

  // 点击图表跳转明细
  chartInstance.on('click', (params) => {
    if (params.name === '通学生') {
      detailTitle.value = '通学生名单'
      detailList.value = stats.day || []
    } else if (params.name === '寄宿生') {
      detailTitle.value = '寄宿生名单'
      detailList.value = stats.boarding || []
    }
    detailDialog.value = true
  })
}

// classId 变化（含首次挂载）即加载统计
watch(() => props.classId, load, { immediate: true })

onBeforeUnmount(() => {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

// 供父组件在保存学生后主动刷新图表
defineExpose({ reload: load })
</script>
