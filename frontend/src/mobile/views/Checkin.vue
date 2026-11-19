<template>
  <div class="m-checkin">
    <van-dropdown-menu>
      <van-dropdown-item v-model="classId" :options="classOptions" @change="onClassChange" />
    </van-dropdown-menu>

    <van-cell-group inset style="margin-top: 8px">
      <van-field
        :model-value="date"
        readonly
        is-link
        label="日期"
        placeholder="选择日期"
        @click="showCalendar = true"
      />
      <van-cell
        title="出勤率统计"
        is-link
        icon="bar-chart-o"
        @click="$router.push('/m/attendance-stats')"
      />
    </van-cell-group>

    <!-- 快捷操作：默认全员出勤，只标异常 -->
    <div class="m-quick" v-if="students.length">
      <van-button size="small" type="primary" plain icon="completed" @click="markAllPresent"
        >全员出勤</van-button
      >
      <van-button size="small" type="warning" plain icon="refresh" @click="markAllAbsent"
        >全员缺勤</van-button
      >
      <span class="m-quick-tip">默认出勤，只点异常学生</span>
    </div>

    <!-- 状态统计 -->
    <div class="m-summary" v-if="students.length">
      <van-tag v-for="s in statusCounts" :key="s.name" :type="statusType(s.name)" size="medium">
        {{ s.name }} {{ s.count }}
      </van-tag>
    </div>

    <!-- 学生列表 -->
    <van-cell-group inset>
      <van-cell
        v-for="s in students"
        :key="s.student_id"
        :title="s.name"
        :label="s.student_no"
        is-link
        @click="pickStatus(s)"
      >
        <template #value>
          <van-tag :type="statusType(s.status)">{{ s.status }}</van-tag>
        </template>
      </van-cell>
    </van-cell-group>
    <!--
      失败提示与空态必须分开（VUE-16）：
      - 名单加载失败时**不能**落成「暂无学生」——那是把网络故障说成业务事实，
        老师会以为这个班没有学生，而不是以为加载挂了。
      - 班级列表失败（classesError）与「真的没带班」也要分开，前者给重试入口。
    -->
    <van-empty v-if="loadError && !students.length" description="加载名单失败">
      <van-button round type="primary" size="small" @click="load">重新加载</van-button>
    </van-empty>
    <van-empty
      v-else-if="!loading && !students.length && !classesLoading"
      :description="emptyText"
    >
      <van-button v-if="classesError" round type="primary" size="small" @click="reloadClasses"
        >重新加载</van-button
      >
    </van-empty>

    <div class="m-footer" v-if="students.length">
      <van-button round block type="primary" :loading="saving" @click="submit">提交点名</van-button>
    </div>

    <van-action-sheet
      v-model:show="showAction"
      :actions="statusActions"
      cancel-text="取消"
      @select="onSelectStatus"
    />
    <van-calendar v-model:show="showCalendar" @confirm="onDateConfirm" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { showToast, showSuccessToast } from '../vant-fn'
import { attendanceApi } from '../../api'
import { formatDate } from '../../utils/date'
import { useClassOptions } from '../composables/useClassOptions'

const { classId, classOptions, classesError, classesLoading, loadClasses, reloadClasses } =
  useClassOptions(load)
const date = ref(formatDate(new Date()))
const students = ref([])
const loading = ref(false)
const saving = ref(false)
const showCalendar = ref(false)
/**
 * 名单是否加载失败。
 *
 * 与「该班真的没有在籍学生」必须分开：原实现是空 `catch`，失败后既不清 `students`
 * 也不留任何标志，页面只能落到「请先选择班级」空态 —— 把网络故障说成了业务事实。
 */
const loadError = ref(false)

const showAction = ref(false)
const currentStudent = ref(null)
const statusActions = [{ name: '出勤' }, { name: '缺勤' }, { name: '请假' }, { name: '迟到' }]

/**
 * 空态文案：四种成因必须区分，否则会互相误导。
 * - 拉不到班级列表（网络/权限）≠ 没带班；
 * - 还没选中班级 ≠ 该班没学生。
 */
const emptyText = computed(() => {
  if (classesError.value) return '班级列表加载失败'
  if (!classOptions.value.length) return '你还没有带班班级'
  if (!classId.value) return '请先选择班级'
  return '该班暂无在籍学生'
})

const statusCounts = computed(() => {
  const map = { 出勤: 0, 缺勤: 0, 请假: 0, 迟到: 0 }
  students.value.forEach((s) => {
    if (map[s.status] !== undefined) map[s.status]++
  })
  return Object.keys(map).map((k) => ({ name: k, count: map[k] }))
})

function statusType(status) {
  return { 出勤: 'success', 缺勤: 'danger', 请假: 'warning', 迟到: 'primary' }[status] || 'default'
}

// 竞态守卫：班级/日期切换并发在途时，旧响应晚到不覆盖新数据
let loadSeq = 0

async function load() {
  if (!classId.value) {
    students.value = []
    loadError.value = false
    return
  }
  const seq = ++loadSeq
  // 固定本次目标：await 期间 classId/date 可能已被改掉，不能用实时值写结果判定
  const targetClassId = classId.value
  const targetDate = date.value
  loading.value = true
  loadError.value = false
  try {
    const res = await attendanceApi.list({ class_id: targetClassId, date: targetDate })
    if (seq !== loadSeq) return
    students.value = res.items || []
  } catch (e) {
    if (seq !== loadSeq) return
    // 只置错误标志、**不清 students**：同班刷新失败时表里仍是本班数据，清空反而
    // 会把「有数据但刷新失败」伪装成空态。换班/换日期的"残留上一班名单"问题由
    // onClassChange / onDateConfirm 在请求前清空解决（见那里的注释）。
    loadError.value = true
    showToast('加载名单失败，请重试')
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

// 一键全员出勤
function markAllPresent() {
  students.value.forEach((s) => {
    s.status = '出勤'
  })
  showToast('已设为全员出勤')
}

// 一键全员缺勤（用于反选：先全缺勤，再把到校的标成出勤）
function markAllAbsent() {
  students.value.forEach((s) => {
    s.status = '缺勤'
  })
  showToast('已设为全员缺勤，请点选到校学生')
}

function pickStatus(s) {
  currentStudent.value = s
  showAction.value = true
}

function onSelectStatus(action) {
  if (currentStudent.value) {
    currentStudent.value.status = action.name
  }
  showAction.value = false
}

/**
 * 换班：**先清空名单再请求**。
 *
 * 换班即换数据集 —— 只请求不清数据的话，「A→B 且 B 的请求失败」会让下拉显示 B 班、
 * 名单还是 A 班的学生。这时老师点「提交」，就是把 A 班的学生按 B 班的 class_id 写库
 * （后端会全部跳过，但原实现仍提示「点名成功」）。先清空后，这种场景天然落到
 * 「无数据 + loadError」分支，与「同班刷新失败（有旧数据）」由数据本身区分。
 */
function onClassChange() {
  students.value = []
  loadError.value = false
  load()
}

/** 换日期：同换班，先清空再请求，避免失败时残留前一天的名单被当成今天的表。 */
function onDateConfirm(d) {
  date.value = formatDate(d)
  showCalendar.value = false
  students.value = []
  loadError.value = false
  load()
}

/**
 * 提交点名：**必须核对后端返回值**。
 *
 * 原实现丢弃 `attendanceApi.checkin` 的返回值并无条件提示「点名成功」。后端对
 * 「不属本班 / 已退学 / 学生不存在」的记录是静默跳过的（`attendance_service.checkin`），
 * 于是一份全错班的 payload 会返回 `count: 0` 而前端照样报成功 —— 当天考勤一条未写库。
 *
 * 现在三档：
 * - `count <= 0`    → 提示失败，绝不报成功；
 * - `count < 总数`  → 提示「仅记录 X/Y 人」（+ 被跳过人数），不报成功；
 * - `count === 总数` → 成功（此时 skipped 必为 0：每条记录非 saved 即 skipped）。
 *
 * 注：Vant 4 的多条 toast 需要全局 `allowMultipleToast(true)`（会影响所有页面），
 * 因此这里把「成功」与「部分失败」合并成**一条**提示，而不是连弹两条互相覆盖。
 */
async function submit() {
  if (!students.value.length) {
    return showToast(loadError.value ? '名单加载失败，请先点「重新加载」' : '暂无学生')
  }
  if (saving.value) return // 防重复点击（:loading 只是视觉，连点仍会触发两次）
  const records = students.value.map((s) => ({ student_id: s.student_id, status: s.status }))
  saving.value = true
  try {
    const res = await attendanceApi.checkin({
      class_id: classId.value,
      date: date.value,
      records,
    })
    const count = Number(res?.count ?? 0)
    const skipped = Number(res?.skipped ?? 0)
    const total = records.length
    if (count <= 0) {
      // 后端一条都没写（典型成因：这份名单其实属于另一个班）——绝不能报「点名成功」
      return showToast('点名未记录任何学生，请检查班级后重试')
    }
    if (count < total) {
      const extra = skipped > 0 ? `，${skipped} 人不在本班未记录` : ''
      return showToast(`仅记录 ${count}/${total} 人${extra}`)
    }
    // count === total ⇒ 全部写入（此时 skipped 必为 0：每条记录非 saved 即 skipped）
    showSuccessToast('点名成功')
  } catch (e) {
    // 后端 4xx/5xx 与网络异常都已由全局拦截器弹出详情，这里只补一条面向老师的收尾提示，
    // 避免"点了提交什么都没发生"。
    showToast('点名提交失败，请重试')
  } finally {
    saving.value = false
  }
}

onMounted(loadClasses)
</script>

<style scoped>
.m-checkin {
  padding-bottom: 80px;
}
.m-summary {
  display: flex;
  gap: 8px;
  padding: 12px 16px 0;
}
.m-quick {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px 0;
  flex-wrap: wrap;
}
.m-quick-tip {
  color: #969799;
  font-size: 12px;
}
.m-footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 50px;
  padding: 12px 16px;
  background: #fff;
}
</style>
