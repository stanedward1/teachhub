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
        <!-- 汇总条 -->
        <div class="sdd-summary">
          <span>应提交 <b>{{ distribution.total }}</b> 人</span>
          <span class="dot">·</span>
          <span>已提交 <b>{{ distribution.submitted_count }}</b> 人</span>
          <span class="dot">·</span>
          <span>未评分 <b class="warn-text">{{ distribution.unscored_count }}</b> 人</span>
          <span class="dot">·</span>
          <span>未交 <b class="danger-text">{{ distribution.unsubmitted_count }}</b> 人</span>
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
import { homeworkApi } from '../api'

/**
 * ScoreDistributionDialog — 作业「分数段分布」公共弹窗（列表页 / 审阅页共用）。
 *
 * 能力：汇总（应提交 / 已提交 / 未评分 / 未交）+ 分类筛选（全部 / 五段 / 未评分 / 未交）
 * + 双评分明细（教师评分 / AI 评分，缺失单元格显示灰「—」，不做整列隐藏）+ 未交单列分区。
 *
 * 数据自持：弹窗打开（或 assignmentId 变化）时按 id 拉取 `score-distribution`，
 * 分类切换**纯前端筛选**、不重新请求（单作业学生量通常 ≤ 百级）。
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

// 打开弹窗（或切换任务）时加载；关闭时不动作
watch(
  () => [props.modelValue, props.assignmentId],
  ([open]) => {
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
  font-size: 14px;
  color: #606266;
  margin-bottom: 14px;
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
