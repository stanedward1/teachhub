<template>
  <el-dialog
    v-model="visible"
    :title="dialogTitle"
    width="760px"
    :close-on-click-modal="false"
  >
    <div v-loading="loading" style="min-height: 120px">
      <!-- 加载失败：内联重试（错误原因已由全局拦截器提示） -->
      <div v-if="error" class="sdd-error">
        <span>数据加载失败</span>
        <el-button link type="primary" @click="load">点击重试</el-button>
      </div>

      <template v-else-if="distribution">
        <!-- 汇总条（左侧统计 + 右侧「AI 综合分析」入口） -->
        <div class="sdd-summary">
          <span>应提交 <b>{{ distribution.total }}</b> 人</span>
          <span class="dot">·</span>
          <span>已提交 <b>{{ distribution.submitted_count }}</b> 人</span>
          <span class="dot">·</span>
          <span>未评分 <b class="warn-text">{{ distribution.unscored_count }}</b> 人</span>
          <span class="dot">·</span>
          <span>未交 <b class="danger-text">{{ distribution.unsubmitted_count }}</b> 人</span>
          <!-- 零提交时禁用：后端同样会 400 短路，前端提前挡住是为了不让人白点一次 -->
          <el-button
            class="sdd-analysis-btn"
            type="primary"
            plain
            size="small"
            :loading="analyzing"
            :disabled="analysisDisabled"
            :title="analysisHint"
            @click="runAnalysis"
          >
            {{ analysis ? '重新分析' : 'AI 综合分析' }}
          </el-button>
        </div>

        <!-- AI 综合分析结果（班级层面归纳；逐生分数仍以下方明细表为准） -->
        <div v-if="analysis" class="sdd-analysis">
          <div class="sdd-analysis-head">
            <span class="sdd-analysis-title">AI 综合分析</span>
            <span class="sdd-analysis-time">{{ formatGeneratedAt(analysis.generated_at) }}</span>
          </div>
          <div class="sdd-analysis-chips">
            <span v-for="chip in analysisChips" :key="chip.label" class="sdd-analysis-chip">
              {{ chip.label }} <b>{{ chip.value }}</b>
            </span>
          </div>
          <Markdown :content="analysis.analysis" />
          <el-collapse v-if="hasAnalysisNotes" class="sdd-analysis-more">
            <el-collapse-item title="参与分析的数据" name="data">
              <div v-if="analysis.omitted_count" class="sdd-analysis-omit">
                本次有 {{ analysis.omitted_count }} 名学生的明细未进入输入预算。
              </div>
              <ul class="sdd-analysis-notes">
                <li v-for="(note, idx) in analysis.budget_notes || []" :key="idx">{{ note }}</li>
              </ul>
            </el-collapse-item>
          </el-collapse>
        </div>

        <!-- 分类筛选：全部 / 五段 / 未评分 / 未交（点击只展示对应学生） -->
        <div class="sdd-filters">
          <button
            v-for="f in filters"
            :key="f.key"
            type="button"
            class="sdd-chip"
            :class="{ active: activeFilter === f.key, warn: f.warn, danger: f.danger }"
            @click="activeFilter = f.key"
          >
            <span class="sdd-chip-name">{{ f.name }}</span>
            <span v-if="f.label" class="sdd-chip-label">{{ f.label }}</span>
            <span class="sdd-chip-count">{{ f.count }}</span>
          </button>
        </div>

        <!-- 明细表：仅展示当前分类的学生 -->
        <div class="sdd-students">
          <div class="sdd-students-title">
            {{ currentFilter ? currentFilter.name : '' }}
            <span v-if="currentFilter && currentFilter.label" class="sdd-students-range">
              （{{ currentFilter.label }} 分）
            </span>
            · {{ currentStudents.length }} 人
          </div>
          <el-table
            v-if="currentStudents.length"
            :data="currentStudents"
            size="small"
            max-height="300"
            style="width: 100%"
          >
            <!-- 姓名可点击（仅已提交学生）：跳转该生「任务完成情况」详情页；
                 未交学生无提交记录（无 submission_id），姓名保持纯文本不可点 -->
            <el-table-column label="姓名" min-width="120">
              <template #default="{ row }">
                <el-button
                  v-if="row.submission_id"
                  link
                  type="primary"
                  title="查看该生任务完成情况"
                  @click="goDetail(row)"
                  >{{ row.name }}</el-button
                >
                <span v-else>{{ row.name }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="student_no" label="学号" width="150" />
            <el-table-column label="教师评分" width="120">
              <template #default="{ row }">
                <span v-if="hasScore(row.teacher_score)" class="score-num">{{
                  row.teacher_score
                }}</span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="AI 评分" width="120">
              <template #default="{ row }">
                <span v-if="hasScore(row.ai_score)" class="score-num ai">{{
                  row.ai_score
                }}</span>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="sdd-empty">{{ emptyText }}</div>
        </div>

        <!-- 未交学生单列展示（常驻分区） -->
        <div class="sdd-unsubmitted">
          <div class="sdd-students-title danger-text">
            未交任务（{{ distribution.unsubmitted.length }} 人）
          </div>
          <template v-if="distribution.unsubmitted.length">
            <div class="sdd-tags">
              <el-tag
                v-for="s in distribution.unsubmitted"
                :key="s.id"
                type="danger"
                effect="plain"
              >
                {{ s.name }}
                <span v-if="s.student_no" class="sdd-tag-no">{{ s.student_no }}</span>
              </el-tag>
            </div>
          </template>
          <div v-else class="muted">全部已提交</div>
        </div>
      </template>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { homeworkApi } from '../api'
import Markdown from './Markdown.vue'

/**
 * ScoreDistributionDialog — 作业「分数段分布」公共弹窗（列表页 / 审阅页共用）。
 *
 * 能力：汇总（应提交 / 已提交 / 未评分 / 未交）+ 分类筛选（全部 / 五段 / 未评分 / 未交）
 * + 双评分明细（教师评分 / AI 评分，缺失单元格显示灰「—」，不做整列隐藏）+ 未交单列分区
 * + **AI 综合分析**（一次调用给出班级层面的总体情况 / 亮点 / 共性问题 / 教学建议）。
 *
 * 数据自持：弹窗打开（或 assignmentId 变化）时按 id 拉取 `score-distribution`，
 * 分类切换**纯前端筛选**、不重新请求（单作业学生量通常 ≤ 百级）。
 *
 * 为什么「AI 综合分析」要二次确认：它和 AI 批改**共用同一个成本池**，一次点击就是
 * 1~2 次真实外呼费用（模型输出被截断时后端会重试一次并补记额度）。误点即花钱，所以
 * 首次分析、重新分析都要确认（文案区分，避免用户以为「重新分析」是免费的本地重算）。
 * 零提交时按钮直接禁用 —— 后端也会 400 短路，前端提前挡住只是少一次无意义的往返。
 *
 * 为什么关闭弹窗/切换任务就清空分析：分析结果绑定了具体任务与生成时刻，若残留，下一次
 * 打开别的任务时会看到上一个任务的结论，比「没有结果」危险得多。
 *
 * 明细表「姓名」可点击（仅已提交学生）→ 跳转该生提交详情页
 * （`/admin/homework/{assignmentId}/submissions/{submissionId}`，即「任务完成情况」）；
 * 未交学生无提交记录（submission_id 为 null），姓名保持纯文本不可点。
 *
 * @prop {Boolean}        modelValue      弹窗显隐（v-model）
 * @prop {Number|String}  assignmentId    目标任务 id（打开 / 变化时触发加载）
 * @prop {String}         assignmentTitle 任务标题（用于弹窗标题）
 * @emits {Boolean} update:modelValue 关闭等显隐变化回写
 */
const props = defineProps({
  modelValue: { type: Boolean, default: false },
  assignmentId: { type: [Number, String], default: null },
  assignmentTitle: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

/** 路由：点击学生姓名跳转该生「任务完成情况」详情页 */
const router = useRouter()

/** v-model 代理：父组件用 v-model 控制显隐 */
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const dialogTitle = computed(() =>
  props.assignmentTitle ? `${props.assignmentTitle} · 分数段分布` : '分数段分布'
)

const distribution = ref(null)
const loading = ref(false)
const error = ref(false)
/** AI 综合分析结果（null = 本次打开还没生成过；关闭弹窗/切换任务时清空） */
const analysis = ref(null)
/** 分析请求进行中（按钮 loading；请求期间禁止重复点击） */
const analyzing = ref(false)
/** 当前分类：'all' | 段 key | 'unscored' | 'unsubmitted' */
const activeFilter = ref('all')

/** 分数是否有效：仅非 null/undefined 才算有分（0 是合法分数，必须展示） */
function hasScore(v) {
  return v !== null && v !== undefined
}

/**
 * 跳转该生「任务完成情况」提交详情页。
 * 仅已提交学生有 submission_id；未交学生（null）不可跳转，直接忽略。
 */
function goDetail(row) {
  if (!row?.submission_id || !props.assignmentId) return
  visible.value = false // 关闭弹窗，避免返回时残留
  router.push(`/admin/homework/${props.assignmentId}/submissions/${row.submission_id}`)
}

/** 分类按钮：全部 + 五段（带人数）+ 未评分 + 未交 */
const filters = computed(() => {
  const d = distribution.value
  if (!d) return []
  const list = [{ key: 'all', name: '全部', label: '', count: d.scored_count }]
  for (const seg of d.segments) {
    list.push({ key: seg.key, name: seg.name, label: seg.label, count: seg.count })
  }
  list.push({ key: 'unscored', name: '未评分', label: '', count: d.unscored_count, warn: true })
  list.push({
    key: 'unsubmitted',
    name: '未交',
    label: '',
    count: d.unsubmitted_count,
    danger: true,
  })
  return list
})

const currentFilter = computed(() => filters.value.find((f) => f.key === activeFilter.value))

/** 当前分类下的学生（已评分按分数倒序） */
const currentStudents = computed(() => {
  const d = distribution.value
  if (!d) return []
  const f = activeFilter.value
  if (f === 'unscored') return d.unscored_students
  if (f === 'unsubmitted') return d.unsubmitted
  let rows = d.scored_students
  if (f !== 'all') {
    const idx = d.segments.findIndex((s) => s.key === f)
    rows = rows.filter((s) => s.segment === idx)
  }
  return [...rows].sort((a, b) => b.score - a.score)
})

const emptyText = computed(() =>
  activeFilter.value === 'unsubmitted' ? '全部已提交，无未交学生' : '该分类暂无学生'
)

/** 分数/百分比文本：后端用 null 表示「无数据」，这里统一显示「—」（0 是合法值，不能隐藏） */
function metricText(v, suffix = '') {
  return v === null || v === undefined ? '—' : `${v}${suffix}`
}

/** 生成时间：ISO 字符串 → 「YYYY-MM-DD HH:mm」（不引入日期库，够用即可） */
function formatGeneratedAt(v) {
  if (!v) return ''
  return String(v).replace('T', ' ').slice(0, 16)
}

/** 分析结果顶部的统计 chips（数字直接取后端 stats，前端不做任何再计算） */
const analysisChips = computed(() => {
  const s = analysis.value && analysis.value.stats
  if (!s) return []
  return [
    { label: '教师均分', value: metricText(s.avg_teacher_score) },
    { label: 'AI 均分', value: metricText(s.avg_ai_score) },
    { label: 'AI 覆盖率', value: metricText(s.ai_reviewed_pct, '%') },
  ]
})

/** 「参与分析的数据」折叠区：没有 omitted_count 也没有说明时不渲染（避免空折叠面板） */
const hasAnalysisNotes = computed(() => {
  const a = analysis.value
  if (!a) return false
  return Boolean(a.omitted_count) || (a.budget_notes || []).length > 0
})

/** 零提交时禁用分析按钮：没有可分析的内容，点了只会 400 */
const analysisDisabled = computed(
  () => !distribution.value || distribution.value.submitted_count === 0
)

const analysisHint = computed(() =>
  analysisDisabled.value
    ? '该任务还没有学生提交，暂无法生成分析'
    : '基于已提交内容与 AI 批改结果生成班级综合评价（每次消耗 1~2 次 AI 额度）'
)

/**
 * 触发 AI 综合分析（后端一次调用给出班级层面评价）。
 *
 * 必须先二次确认再发请求：额度是真金白银，取消时**一个请求都不发**。
 * 文案写「1~2 次」不是保守说法：模型输出被截断时后端会自动重试一次并补记额度
 * （见 `ai_grading._call_model` 的 `_record_extra_grade_call`），所以一次点击最多扣 2 次。
 * 结果按「发起时的 assignmentId」校对后才落盘 —— 请求期间的切换任务不能让旧结果
 * 显示在新任务下。
 */
async function runAnalysis() {
  if (!props.assignmentId || analyzing.value || analysisDisabled.value) return
  const confirmText = analysis.value
    ? '重新分析将再次消耗 1~2 次 AI 额度，是否继续？'
    : '本次分析将消耗 1 次 AI 调用额度（模型输出被截断时会自动重试，最多 2 次），是否继续？'
  try {
    await ElMessageBox.confirm(confirmText, 'AI 综合分析', { type: 'info' })
  } catch (e) {
    return // 用户取消：不发请求
  }
  const targetId = props.assignmentId
  analyzing.value = true
  try {
    const result = await homeworkApi.analyzeAssignment(targetId)
    // 期间切换了任务/关闭了弹窗 ⇒ 丢弃本次结果（错误提示由全局拦截器负责）
    if (String(props.assignmentId) === String(targetId)) analysis.value = result
  } catch (e) {
    // 错误交给全局拦截器提示，这里只保证按钮 loading 复位
  } finally {
    analyzing.value = false
  }
}

/** 清空分析结果与进行中状态（关闭弹窗 / 切换任务时必须调用） */
function resetAnalysis() {
  analysis.value = null
  analyzing.value = false
}

async function load() {
  if (!props.assignmentId) return
  loading.value = true
  error.value = false
  try {
    distribution.value = await homeworkApi.scoreDistribution(props.assignmentId)
    activeFilter.value = 'all'
  } catch (e) {
    distribution.value = null
    error.value = true
  } finally {
    loading.value = false
  }
}

// 打开弹窗（或切换任务）时加载；关闭时清空分析结果 —— 残留会把 A 任务的结论显示在 B 任务下
watch(
  () => [props.modelValue, props.assignmentId],
  ([open]) => {
    resetAnalysis()
    if (open) load()
  }
)
</script>

<style scoped>
.muted {
  color: #9ca3af;
  font-size: 13px;
}
.sdd-error {
  padding: 24px 0;
  text-align: center;
  color: #909399;
}
.sdd-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  row-gap: 8px;
  font-size: 14px;
  color: #606266;
  margin-bottom: 14px;
}
.sdd-analysis-btn {
  margin-left: auto;
}
.sdd-analysis {
  padding: 14px 16px;
  margin-bottom: 14px;
  background: #f8fafc;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
}
.sdd-analysis-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
}
.sdd-analysis-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}
.sdd-analysis-time {
  font-size: 12px;
  color: #9ca3af;
}
.sdd-analysis-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.sdd-analysis-chip {
  padding: 3px 10px;
  font-size: 12px;
  color: #606266;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 12px;
}
.sdd-analysis-chip b {
  color: var(--el-color-primary);
}
.sdd-analysis-more {
  margin-top: 10px;
  --el-collapse-header-bg-color: transparent;
  --el-collapse-content-bg-color: transparent;
}
.sdd-analysis-omit {
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--el-color-warning);
}
.sdd-analysis-notes {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: #909399;
}
.sdd-summary b {
  color: #303133;
}
.sdd-summary .warn-text {
  color: var(--el-color-warning);
}
.sdd-summary .danger-text {
  color: var(--el-color-danger);
}
.sdd-summary .dot {
  margin: 0 8px;
  color: #c0c4cc;
}
.sdd-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}
.sdd-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  font-size: 13px;
  color: #303133;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.2s;
}
.sdd-chip:hover {
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}
.sdd-chip.active {
  background: var(--el-color-primary);
  border-color: var(--el-color-primary);
  color: #fff;
}
.sdd-chip.active .sdd-chip-label,
.sdd-chip.active .sdd-chip-count {
  color: #fff;
}
.sdd-chip.warn .sdd-chip-count {
  color: var(--el-color-warning);
}
.sdd-chip.danger .sdd-chip-count {
  color: var(--el-color-danger);
}
.sdd-chip.active.warn .sdd-chip-count,
.sdd-chip.active.danger .sdd-chip-count {
  color: #fff;
}
.sdd-chip-label {
  color: #909399;
  font-size: 12px;
}
.sdd-chip-count {
  font-weight: 600;
  color: var(--el-color-primary);
}
.sdd-students-title {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 8px;
}
.sdd-students-range {
  color: #909399;
  font-weight: 400;
}
.sdd-empty {
  padding: 20px 0;
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
  background: #fafafa;
  border-radius: 6px;
}
.score-num {
  font-weight: 600;
  color: #303133;
}
.score-num.ai {
  color: var(--el-color-primary);
}
.sdd-unsubmitted {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px dashed #ebeef5;
}
.danger-text {
  color: var(--el-color-danger);
}
.sdd-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.sdd-tag-no {
  margin-left: 6px;
  opacity: 0.65;
  font-size: 12px;
}
</style>
