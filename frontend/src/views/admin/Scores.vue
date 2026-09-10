<template>
  <div>
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- 成绩列表 -->
      <el-tab-pane label="成绩列表" name="list">
        <div class="toolbar">
          <el-input v-model="subject" placeholder="按科目筛选" clearable style="width: 180px" @clear="load" />
          <StudentSelect v-model="studentId" v-model:class-id="classId" show-class-filter placeholder="按学生筛选" style="width: 320px" @update:model-value="load" @update:class-id="load" />
          <el-button @click="load">查询</el-button>
          <div class="spacer"></div>
          <el-button @click="downloadTemplate">下载模板</el-button>
          <el-button type="success" @click="openImport">批量导入</el-button>
          <el-button @click="exportExcel">导出成绩单</el-button>
          <el-button type="primary" @click="openCreate">录入成绩</el-button>
          <SortBar v-model="order" />
        </div>

        <div class="page-card">
          <el-table :data="items" v-loading="loading" style="width: 100%">
            <el-table-column label="学生" width="120">
              <template #default="{ row }">
                <el-link type="primary" :underline="false" @click="openStudentCard(row)">{{ row.student_name }}</el-link>
              </template>
            </el-table-column>
            <el-table-column prop="student_no" label="学号" width="120" />
            <el-table-column prop="subject" label="科目" width="160" />
            <el-table-column prop="score" label="成绩" width="100" />
            <el-table-column prop="exam_name" label="考试名称" width="140" />
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
                <el-button link type="danger" @click="remove(row)">删除</el-button>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="暂无成绩记录">
                <el-button type="primary" @click="openCreate">录入第一条成绩</el-button>
              </el-empty>
            </template>
          </el-table>
          <PaginationBar v-model:page="page" v-model:page-size="pageSize" :total="total" @change="load" />
        </div>
      </el-tab-pane>

      <!-- 成绩分析 -->
      <el-tab-pane label="成绩分析" name="analysis">
        <div class="toolbar">
          <StudentSelect v-model="analysisClassId" show-class-filter placeholder="选择班级" style="width: 280px" @update:model-value="loadAnalysis" />
          <el-select v-model="analysisSubject" placeholder="全部科目" clearable filterable style="width: 160px" @change="loadAnalysis">
            <el-option v-for="s in analysisSubjects" :key="s" :label="s" :value="s" />
          </el-select>
          <el-select v-model="analysisExam" placeholder="全部考试" clearable filterable style="width: 180px" @change="loadAnalysis">
            <el-option v-for="e in analysisExams" :key="e" :label="e" :value="e" />
          </el-select>
          <el-button @click="loadAnalysis">查询</el-button>
        </div>

        <div class="page-card" v-loading="analysisLoading">
          <div class="analysis-head">
            <h3 class="card-title" style="margin: 0;">班级成绩排名</h3>
            <span v-if="ranking.length" style="color: var(--text-tertiary); font-size: 13px;">共 {{ ranking.length }} 人（按{{ analysisSubject || '全部科目' }}均分排名）</span>
          </div>
          <el-table :data="ranking" style="width: 100%">
            <el-table-column label="名次" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.rank <= 3 ? 'warning' : 'info'" size="small" effect="light">{{ row.rank }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="学生" width="140" />
            <el-table-column prop="student_no" label="学号" width="120" />
            <el-table-column prop="score" label="均分" width="100">
              <template #default="{ row }">
                <span style="font-weight: 600; color: #2563eb;">{{ row.score }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="count" label="记录数" width="100" />
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="viewTrend(row)">查看趋势</el-button>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="该班级暂无成绩，请先在成绩列表录入" />
            </template>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 学生成绩趋势弹窗 -->
    <el-dialog v-model="trendDialog" :title="`${trendName} 的成绩趋势`" width="760px">
      <div ref="trendChartRef" style="width: 100%; height: 360px;"></div>
      <div v-if="!trendData.length" class="empty-state">该学生暂无成绩记录</div>
    </el-dialog>

    <!-- 跨模块学生卡片 -->
    <StudentCard v-model:visible="studentCardVisible" :student-id="studentCardId" />

    <el-dialog v-model="dialog" :title="editing ? '编辑成绩' : '录入成绩'" width="440px">
      <el-form label-width="80px">
        <el-form-item label="学生" required><StudentSelect v-model="form.student_id" show-class-filter /></el-form-item>
        <el-form-item label="科目" required><el-input v-model="form.subject" /></el-form-item>
        <el-form-item label="成绩" required><el-input-number v-model="form.score" :min="0" :max="100" /></el-form-item>
        <el-form-item label="考试名称"><el-input v-model="form.exam_name" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入成绩弹窗 -->
    <el-dialog v-model="importDialog" title="批量导入成绩" width="560px" @close="resetImport">
      <el-form label-width="80px">
        <el-form-item label="导入模板">
          <el-button type="primary" link @click="downloadTemplate">下载标准模板</el-button>
          <span style="color: #909399; font-size: 12px; margin-left: 8px;">请按模板格式填写数据</span>
        </el-form-item>
        <el-form-item label="选择文件">
          <el-upload
            ref="importUploadRef"
            :auto-upload="false"
            :limit="1"
            :on-change="onImportFileChange"
            :on-remove="onImportFileRemove"
            :before-upload="() => false"
            accept=".xlsx,.xls"
            drag
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">将 Excel 文件拖到此处，或<em>点击选择</em></div>
            <template #tip>
              <div class="upload-tip">仅支持 .xlsx / .xls 格式</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <div v-if="importResult" class="import-result">
        <el-alert
          :title="`导入完成：成功 ${importResult.success} 条，失败 ${importResult.errors?.length || 0} 条`"
          :type="importResult.errors?.length ? 'warning' : 'success'"
          :closable="false"
          show-icon
          style="margin-bottom: 12px"
        />
        <div v-if="importResult.errors?.length" class="error-list">
          <div v-for="(err, i) in importResult.errors" :key="i" class="error-item">{{ err }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="importDialog = false">关闭</el-button>
        <el-button type="primary" :loading="importing" @click="doImport">
          {{ importing ? '导入中...' : '开始导入' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import StudentSelect from '../../components/StudentSelect.vue'
import SortBar from '../../components/SortBar.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import StudentCard from '../../components/StudentCard.vue'
import { useSort } from '../../composables/useSort.js'
import { scoreApi } from '../../api'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const activeTab = ref('list')

const rawItems = ref([])
const { order, useSorted } = useSort('scores')
const items = useSorted(rawItems)
const subject = ref('')
const studentId = ref(null)
const classId = ref(null)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = reactive({ student_id: null, subject: '', score: 0, exam_name: '' })

// 成绩分析
const analysisClassId = ref(null)
const analysisSubject = ref('')
const analysisExam = ref('')
const analysisSubjects = ref([])
const analysisExams = ref([])
const ranking = ref([])
const analysisLoading = ref(false)

// 趋势弹窗
const trendDialog = ref(false)
const trendName = ref('')
const trendData = ref([])
const trendChartRef = ref(null)
let trendChart = null

// 跨模块学生卡片
const studentCardVisible = ref(false)
const studentCardId = ref(null)
function openStudentCard(row) {
  if (!row.student_id) return
  studentCardId.value = row.student_id
  studentCardVisible.value = true
}

// 批量导入
const importDialog = ref(false)
const importUploadRef = ref(null)
const importing = ref(false)
const importFile = ref(null)
const importResult = ref(null)

onMounted(load)

async function load() {
  loading.value = true
  try {
    const res = await scoreApi.list({ page: page.value, page_size: pageSize.value, subject: subject.value, student_id: studentId.value, class_id: classId.value })
    rawItems.value = res.items
    total.value = res.total
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function onTabChange(name) {
  if (name === 'analysis') {
    loadAnalysisOptions()
  }
}

async function loadAnalysisOptions() {
  // 拉取可选科目/考试（不指定班级时返回当前教师可见范围内的全部）
  try {
    const res = await scoreApi.analysis({})
    analysisSubjects.value = res.subjects || []
    analysisExams.value = res.exams || []
  } catch (e) {
  }
}

async function loadAnalysis() {
  if (!analysisClassId.value) return
  analysisLoading.value = true
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
  } catch (e) {
  }
}

function renderTrendChart() {
  if (!trendChartRef.value || !trendData.value.length) return
  if (trendChart) { trendChart.dispose(); trendChart = null }
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
      name: subj, type: 'line', smooth: true, data: d.scores,
      lineStyle: { width: 2 }, itemStyle: { color: colorFor(subj) },
      symbol: 'circle', symbolSize: 6,
    })
    if (d.avgs.some(v => v != null)) {
      legendData.push(`${subj}·班级均分`)
      series.push({
        name: `${subj}·班级均分`, type: 'line', data: d.avgs,
        lineStyle: { type: 'dashed', width: 1.5, color: colorFor(subj) },
        itemStyle: { color: colorFor(subj) }, symbol: 'none',
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
    xAxis: { type: 'category', data: xData, axisLabel: { color: '#9ca3af', fontSize: 11, rotate: 20 } },
    yAxis: { type: 'value', min: 0, max: 100, splitLine: { lineStyle: { color: '#f3f4f6' } }, axisLabel: { color: '#9ca3af', fontSize: 11 } },
    series,
  })
}

const COLOR_PALETTE = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4', '#ec4899', '#84cc16']
function colorFor(subj) {
  let h = 0
  for (let i = 0; i < subj.length; i++) h = (h * 31 + subj.charCodeAt(i)) % 997
  return COLOR_PALETTE[h % COLOR_PALETTE.length]
}

function openCreate() {
  editing.value = null
  Object.assign(form, { student_id: null, subject: '', score: 0, exam_name: '' })
  dialog.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, row)
  dialog.value = true
}

async function save() {
  if (!form.student_id || !form.subject) return ElMessage.warning('请选择学生并填写科目')
  saving.value = true
  try {
    if (editing.value) await scoreApi.update(editing.value.id, form)
    else await scoreApi.create(form)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm('确定删除该成绩记录吗？', '提示', { type: 'warning' })
  await scoreApi.remove(row.id)
  ElMessage.success('删除成功')
  load()
}

async function exportExcel() {
  const res = await scoreApi.export({ student_id: studentId.value, class_id: classId.value })
  const blob = new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '成绩单.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}

// 批量导入
function downloadTemplate() {
  scoreApi.template().then(res => {
    const blob = new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '成绩导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  })
}

function openImport() {
  resetImport()
  importDialog.value = true
}

function resetImport() {
  importFile.value = null
  importResult.value = null
  importUploadRef.value?.clearFiles()
}

function onImportFileChange(file) {
  importFile.value = file.raw
  importResult.value = null
}

function onImportFileRemove() {
  importFile.value = null
}

async function doImport() {
  if (!importFile.value) return ElMessage.warning('请选择文件')
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    const res = await scoreApi.import(fd)
    importResult.value = res
    if (res.success > 0) {
      ElMessage.success(`成功导入 ${res.success} 条数据`)
      load()
    }
  } catch (e) {
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.analysis-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.upload-icon {
  font-size: 48px;
  color: var(--brand-light);
}
.upload-text {
  color: var(--text-secondary);
  font-size: 14px;
  margin-top: 8px;
}
.upload-text em {
  color: var(--brand);
  font-style: normal;
}
.upload-tip {
  color: var(--text-tertiary);
  font-size: 12px;
  margin-top: 4px;
}
.import-result {
  margin-top: 16px;
}
.error-list {
  max-height: 200px;
  overflow-y: auto;
  background: #fef2f2;
  border-radius: 8px;
  padding: 12px;
}
.error-item {
  font-size: 13px;
  color: #dc2626;
  line-height: 1.8;
  padding: 2px 0;
}
</style>