<template>
  <div>
    <!-- 背景：/admin/leaves 原本的菜单文案是「考勤管理」，实际只是请假登记页（RBT-124）。
         真正的考勤能力（点名 + 统计）此前只有移动端 /m/checkin 与 /m/attendance-stats，
         PC 管理端完全没有入口 —— 本页补上，并把 /admin/leaves 正名为「请假管理」。 -->
    <!-- 班级列表是两页签共用的数据集：它失败时整页都无法取数，故提示条放在 tabs 之外（全局一条） -->
    <el-alert
      v-if="classesError"
      class="refresh-alert"
      type="error"
      :closable="false"
      show-icon
      title="班级列表加载失败"
    >
      <el-button link type="primary" size="small" @click="loadClasses">重试</el-button>
    </el-alert>

    <el-tabs v-model="activeTab" class="att-tabs" @tab-change="onTabChange">
      <!-- ============ 页签 1：点名 ============ -->
      <el-tab-pane label="点名" name="checkin">
        <div class="toolbar">
          <el-select
            v-model="classId"
            placeholder="选择班级"
            style="width: 200px"
            @change="onClassChange"
          >
            <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
          <el-date-picker
            v-model="date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            style="width: 160px"
            :clearable="false"
            @change="onDateChange"
          />
          <div class="spacer"></div>
          <el-button :disabled="!items.length || loading" @click="markAll('出勤')"
            >全员出勤</el-button
          >
          <el-button :disabled="!items.length || loading" @click="markAll('缺勤')"
            >全员缺勤</el-button
          >
          <el-button
            type="primary"
            :loading="saving"
            :disabled="saving || loading || !items.length"
            @click="submit"
            >提交点名</el-button
          >
        </div>

        <div class="page-card">
          <!-- 当前状态计数：始终基于表格内的实际数据，改一行即变，不用等提交 -->
          <div v-if="items.length" class="status-bar">
            <el-tag
              v-for="s in statusCounts"
              :key="s.name"
              :type="s.type"
              effect="light"
              size="small"
              >{{ s.name }} {{ s.count }}</el-tag
            >
            <span class="status-hint">
              未点名的学生后端默认按「出勤」返回，所以默认全员出勤 = 不改状态直接提交；
              「全员缺勤」用于先把整体置为缺勤、再逐行点出已到校的学生。
            </span>
          </div>

          <!-- 失败提示条：仅在「成功加载过一次」之后接管失败提示（首屏失败交给 StateView 错误态，
               两者不重复）。不能指望 StateView 的 :error —— `revealed` 一旦为 true 它就不再显示错误态。 -->
          <el-alert
            v-if="error && checkinEverLoaded"
            class="refresh-alert"
            type="warning"
            :closable="false"
            show-icon
            :title="checkinAlertText"
          >
            <el-button link type="primary" size="small" @click="loadCheckin">重试</el-button>
          </el-alert>

          <StateView
            :loading="loading || classesLoading"
            :error="error && !items.length"
            :empty="!items.length && !error"
            :columns="3"
            :empty-description="checkinEmptyText"
            @retry="loadCheckin"
          >
            <el-table :data="items" v-loading="loading" style="width: 100%">
              <el-table-column prop="name" label="姓名" min-width="140" />
              <el-table-column prop="student_no" label="学号" min-width="160" />
              <el-table-column label="状态" width="180">
                <template #default="{ row }">
                  <el-select v-model="row.status" size="small" style="width: 120px">
                    <el-option v-for="s in STATUS_LIST" :key="s" :label="s" :value="s" />
                  </el-select>
                </template>
              </el-table-column>
            </el-table>
          </StateView>
        </div>
      </el-tab-pane>

      <!-- ============ 页签 2：统计 ============ -->
      <el-tab-pane label="统计" name="stats">
        <div class="toolbar">
          <!-- 与点名页签联动同一个 classId（两个下拉永远指向同一个班） -->
          <el-select
            v-model="classId"
            placeholder="选择班级"
            style="width: 200px"
            @change="onClassChange"
          >
            <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
          <el-radio-group v-model="range" @change="onPresetChange">
            <el-radio-button value="7">近 7 天</el-radio-button>
            <el-radio-button value="30">近 30 天</el-radio-button>
          </el-radio-group>
          <el-date-picker
            v-model="customRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 270px"
            @change="onCustomChange"
          />
        </div>

        <div class="page-card">
          <!-- 失败提示条：同点名页签，仅「成功加载过一次」后由它接管（首屏失败交给 StateView） -->
          <el-alert
            v-if="statsError && statsEverLoaded"
            class="refresh-alert"
            type="warning"
            :closable="false"
            show-icon
            :title="statsAlertText"
          >
            <el-button link type="primary" size="small" @click="loadSummary">重试</el-button>
          </el-alert>

          <StateView
            :loading="statsLoading || classesLoading"
            :error="statsError && !summary"
            :empty="!summary && !statsError"
            :columns="4"
            :empty-description="statsEmptyText"
            @retry="loadSummary"
          >
            <template v-if="summary">
              <!-- 汇总卡：出勤率大字号 + 口径说明 -->
              <div class="rate-card">
                <div class="rate-num" :style="{ color: rateColor(summary.attendance_rate) }">
                  {{ summary.attendance_rate }}%
                </div>
                <div class="rate-label">出勤率</div>
                <div class="rate-sub">
                  在籍 {{ summary.student_count }} 人 · 记录 {{ summary.total }} 人次
                </div>
                <div class="rate-range">{{ dateRange.start_date }} 至 {{ dateRange.end_date }}</div>
              </div>

              <!-- 状态分布 -->
              <div class="stat-grid">
                <div v-for="s in STATUS_CARDS" :key="s.name" class="stat-cell">
                  <div class="stat-num" :style="{ color: s.color }">
                    {{ summary.status_count[s.name] || 0 }}
                  </div>
                  <div class="stat-label">{{ s.name }}</div>
                </div>
              </div>

              <!-- 逐日趋势 -->
              <div class="card-title">逐日趋势</div>
              <el-table
                :data="summary.trend"
                v-loading="statsLoading"
                class="trend-table"
                style="width: 100%"
              >
                <el-table-column prop="date" label="日期" width="150" />
                <el-table-column
                  v-for="s in STATUS_CARDS"
                  :key="s.name"
                  :label="s.name"
                  width="110"
                >
                  <template #default="{ row }">
                    <span :style="{ color: s.color }">{{ row[s.name] }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="出勤率" width="120">
                  <template #default="{ row }">
                    <span :style="{ color: rateColor(row.rate) }">{{ row.rate }}%</span>
                  </template>
                </el-table-column>
                <template #empty>
                  <div class="trend-empty">暂无考勤数据</div>
                </template>
              </el-table>
            </template>
          </StateView>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import StateView from '../../components/StateView.vue'
import { attendanceApi, studentApi } from '../../api'
import { formatDate } from '../../utils/date'

/**
 * PC 端考勤（RBT-124）：点名 + 出勤率统计。
 *
 * 数据口径（后端 `services/attendance_service.py`）：
 * - `list`：返回该班**在籍**学生，未点名的默认「出勤」；
 * - `checkin`：按 student_id upsert，仅接受本班在籍学生；
 * - `summary`：在籍人数 + 区间内状态分布 + 逐日趋势。
 *
 * 权限口径（`app/permissions.py:197-210` `is_teacher_class_owner`）：
 * 「`Classroom.teacher_id` == 教师 **或** `class_teacher` 表存在该 (class_id, 教师) 行」，
 * 即**班主任 ∪ 科任老师**都放行，与「学校管理员及以上」并列 —— 科任老师访问返回 200，
 * 不是 403。因此菜单项**不设 `need`**（见 menuConfig.js 同处注释）；页面自身的越权防线是
 * 「班级下拉只列 `GET /api/classrooms` 给的班（同样按班主任 ∪ 科任过滤）+ 后端再 403 兜底」。
 */

/** 四态枚举，顺序即页面展示顺序（与后端 ATTENDANCE_STATUS 一致）。 */
const STATUS_LIST = ['出勤', '缺勤', '请假', '迟到']

/** 状态 -> el-tag 配色。 */
const STATUS_TAG_TYPE = { 出勤: 'success', 缺勤: 'danger', 请假: 'warning', 迟到: 'primary' }

/** 统计卡/趋势列的状态与配色（数字色，与 tag 语义一致）。 */
const STATUS_CARDS = [
  { name: '出勤', color: '#16a34a' },
  { name: '缺勤', color: '#dc2626' },
  { name: '请假', color: '#f59e0b' },
  { name: '迟到', color: '#2563eb' },
]

const activeTab = ref('checkin')
const classes = ref([])
/** 班级下拉是否在请求中：此时表格区应显示骨架屏，而不是「没有可选的班」类文案。 */
const classesLoading = ref(false)
/**
 * 班级列表是否加载失败。
 *
 * 必须与「教师真的没带班」区分开：`/api/classrooms` 失败时 classes 也是空数组，
 * 若不单独标记，页面会断言「你还没有带班班级」——把网络故障说成业务事实，且没有重试入口。
 */
const classesError = ref(false)
/** 两个页签共用同一个班级选择（切换页签不会丢上下文）。 */
const classId = ref(null)

// ---------- 点名页签状态 ----------
/** 默认今天：与移动端 Checkin 一致，早读点名基本只点当天。 */
const date = ref(formatDate(new Date()))
const items = ref([])
const loading = ref(false)
const error = ref(false)
const saving = ref(false)

// ---------- 统计页签状态 ----------
const range = ref('7')
/** 自定义区间优先于快捷键；置空则回落到快捷键区间。 */
const customRange = ref([])
const summary = ref(null)
const statsLoading = ref(false)
const statsError = ref(false)

/**
 * 「最后一次请求胜出」序号守卫（本仓库既有约定，见 mobile/views/Checkin.vue）。
 * 班级/日期快速切换时会并发在途，旧响应晚到不得覆盖新数据 ——
 * 否则点名表可能显示 A 班的名单、class_id 却是 B 班，提交即写错班。
 */
let checkinSeq = 0
let statsSeq = 0

/**
 * 已成功加载的「班级|日期」key。
 *
 * 双职责：
 * 1. 切页签时判断是否需要重新取数（key 相同则跳过，避免抹掉老师已改的状态）；
 * 2. 提交前二次确认「表里的名单确实属于当前班级+日期」，防止切班在途时错班写库。
 */
let checkinLoadedKey = ''
let statsLoadedKey = ''

/**
 * 两个页签各自「是否成功加载过一次」。
 *
 * 用来决定失败提示归谁显示（永不复位）：
 * - 从未成功过 → 首屏失败，交给 `StateView` 的错误态（此时 `revealed=false`，错误态正常显示）；
 * - 成功过再失败 → `revealed` 已为 true，`StateView` 的错误态永不再出现，
 *   由页面顶部的 `.refresh-alert` 承担（含「重试」）。
 * 不能改用「items 是否为空」判断：空班（成功加载但 0 学生）会被误判成首屏失败，
 * 导致换班失败时零提示、也没有重试入口。
 */
let checkinEverLoaded = false
let statsEverLoaded = false

const statusCounts = computed(() => {
  const map = { 出勤: 0, 缺勤: 0, 请假: 0, 迟到: 0 }
  items.value.forEach((s) => {
    if (map[s.status] !== undefined) map[s.status] += 1
  })
  return STATUS_LIST.map((name) => ({ name, count: map[name], type: STATUS_TAG_TYPE[name] }))
})

/**
 * 点名页签的空态文案：三种成因必须区分，否则会互相误导。
 * - 不带任何班的教师（如纯行政/新入职）**永久**看到「该班暂无在籍学生」是错的；
 * - 首屏 /api/classrooms 在途或班级未选中时也不该说「该班无学生」。
 */
const checkinEmptyText = computed(() => {
  // 只陈述事实，不写「请重试」：重试入口统一由 el-tabs 之外那条全局横幅承载，
  // 两处都强调会变成同一件事说两遍（横幅红条 + 空态文案 + 按钮 = 页面像没做完）
  if (classesError.value) return '班级列表加载失败'
  if (!classes.value.length) return '你还没有带班班级，无法点名'
  if (!classId.value) return '请先选择班级'
  return '该班暂无在籍学生'
})

/** 统计页签的空态文案，成因划分同上（末态是「有班但没有考勤记录」）。 */
const statsEmptyText = computed(() => {
  if (classesError.value) return '班级列表加载失败'
  if (!classes.value.length) return '你还没有带班班级'
  if (!classId.value) return '请先选择班级'
  return '暂无考勤数据'
})

/**
 * 失败提示条文案：有无旧数据说法不同。
 *
 * 为什么必须自己起一条 banner：`StateView` 的 `showError = error && !revealed`，
 * 首屏成功过一次后 `revealed` 永为 true，`:error` 再也不会渲染错误态 —— 「有内容后刷新失败」
 * 只能靠这条行内提示 + 重试，否则会静默显示旧数据。
 */
const checkinAlertText = computed(() =>
  items.value.length ? '刷新失败，当前显示的是上次加载的数据' : '加载失败，请重试'
)

const statsAlertText = computed(() =>
  summary.value ? '刷新失败，当前显示的是上次加载的数据' : '加载失败，请重试'
)

/** 统计区间：自定义区间优先，否则按快捷键回推「近 N 天」（含今天）。 */
const dateRange = computed(() => {
  const custom = customRange.value
  if (Array.isArray(custom) && custom.length === 2 && custom[0] && custom[1]) {
    return { start_date: custom[0], end_date: custom[1] }
  }
  const days = range.value === '30' ? 30 : 7
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - (days - 1))
  return { start_date: formatDate(start), end_date: formatDate(end) }
})

/** 出勤率配色：≥95 绿、≥85 橙、否则红（两处共用同一套规则）。 */
function rateColor(rate) {
  const value = Number(rate) || 0
  if (value >= 95) return '#16a34a'
  if (value >= 85) return '#f59e0b'
  return '#dc2626'
}

/** 当前「班级|日期」标识，用于与 {@link checkinLoadedKey} 比对。 */
function checkinKeyNow() {
  return `${classId.value}|${date.value}`
}

/** 当前「班级|区间」标识，用于与 {@link statsLoadedKey} 比对。 */
function statsKeyNow() {
  const { start_date, end_date } = dateRange.value
  return `${classId.value}|${start_date}|${end_date}`
}

/** 拉取未毕业班级；管理员看全部，班主任只看自己带的班（后端已按角色过滤）。 */
async function loadClasses() {
  classesLoading.value = true
  classesError.value = false
  try {
    const res = await studentApi.classrooms({ graduated: 'false' })
    classes.value = res.items || []
  } catch (e) {
    // 全局拦截器已提示；这里标记「列表没拿到」，让空态说真话并给出重试入口
    classesError.value = true
    classes.value = []
  } finally {
    classesLoading.value = false
  }
  if (classes.value.length && !classId.value) {
    classId.value = classes.value[0].id
    await loadCheckin()
  }
}

/** 加载点名名单（含未点名的默认「出勤」）。 */
async function loadCheckin() {
  if (!classId.value) {
    items.value = []
    error.value = false
    checkinLoadedKey = ''
    return
  }
  const seq = ++checkinSeq
  // 固定本次目标：await 期间 classId/date 可能已被改掉，不能用实时值写结果判定
  const targetClassId = classId.value
  const targetDate = date.value
  loading.value = true
  error.value = false
  try {
    const res = await attendanceApi.list({ class_id: targetClassId, date: targetDate })
    if (seq !== checkinSeq) return
    // 拷贝成新对象：后端的行是响应数据，改 status 不应回写别名对象
    items.value = (res.items || []).map((s) => ({ ...s }))
    checkinLoadedKey = `${targetClassId}|${targetDate}`
    checkinEverLoaded = true
  } catch (e) {
    if (seq !== checkinSeq) return
    // 只置错误标志：**不清 items、也不写 checkinLoadedKey**。
    // - 保留 items：`StateView` 的 error 态条件是 `error && !revealed`，首屏成功过之后
    //   永不再显示；若这里清空，同班刷新失败会被伪装成空态「该班暂无在籍学生」且无重试入口。
    // - 保留 key：submit() 的「名单是否属于当前班级/日期」校验依赖它。同班刷新失败时表里
    //   就是本班数据，允许提交；若在这里清空 key，会把老师误判成「名单还在加载」并挡住提交。
    // - 换班/换日期的「残留旧班名单」问题不靠这里解决：onClassChange / onDateChange 已在
    //   请求前清空 items 与 key，所以那两种失败天然落在「无数据 + error」分支。
    // - 首屏失败（items 本就为空）由 StateView 错误态 + @retry 承担；全局拦截器已弹过详情。
    error.value = true
  } finally {
    if (seq === checkinSeq) loading.value = false
  }
}

/** 加载统计汇总。 */
async function loadSummary() {
  if (!classId.value) {
    summary.value = null
    statsError.value = false
    statsLoadedKey = ''
    return
  }
  const seq = ++statsSeq
  const targetClassId = classId.value
  const { start_date, end_date } = dateRange.value
  statsLoading.value = true
  statsError.value = false
  try {
    const res = await attendanceApi.summary({
      class_id: targetClassId,
      start_date,
      end_date,
    })
    if (seq !== statsSeq) return
    summary.value = res
    statsLoadedKey = `${targetClassId}|${start_date}|${end_date}`
    statsEverLoaded = true
  } catch (e) {
    if (seq !== statsSeq) return
    // 同 loadCheckin：保留 summary 与 statsLoadedKey，只置错误标志。
    // 换班/换区间残留的旧汇总由 onClassChange / onPresetChange / onCustomChange 在请求前
    // 清空 summary 解决（那里已把 summary 置 null），不在这里清。
    statsError.value = true
  } finally {
    if (seq === statsSeq) statsLoading.value = false
  }
}

/**
 * 班级变更：**先清空再请求**。
 *
 * 换班即换数据集 —— 只清 key 不清数据的话，「A→B 且 B 的请求失败」会让下拉显示 B 班、
 * 表格里仍是 A 班学生（提交虽被 key 校验拦住，但界面在骗人）。先清空后，这种场景天然
 * 落到「无数据 + error」分支，与「同班刷新失败（有旧数据）」由数据本身区分，无需标志位。
 */
function onClassChange() {
  items.value = []
  summary.value = null
  checkinLoadedKey = ''
  statsLoadedKey = ''
  if (activeTab.value === 'stats') loadSummary()
  else loadCheckin()
}

/** 换日期：同换班，先清空再请求，避免失败时残留前一天名单被当成今天的表。 */
function onDateChange() {
  items.value = []
  loadCheckin()
}

/** 切页签：目标页签数据未就绪（含换了班级）时才取数，避免抹掉已有编辑。 */
function onTabChange(name) {
  if (!classId.value) return
  if (name === 'stats') {
    if (statsLoadedKey !== statsKeyNow()) loadSummary()
  } else if (checkinLoadedKey !== checkinKeyNow()) {
    loadCheckin()
  }
}

/** 快捷键区间：清掉自定义区间，二者只保留一个生效来源；区间同理先清空再请求。 */
function onPresetChange() {
  customRange.value = []
  summary.value = null
  loadSummary()
}

/** 自定义区间：选中则接管（取消则回落到快捷键区间）。 */
function onCustomChange(value) {
  if (Array.isArray(value) && value.length === 2) {
    range.value = ''
  } else {
    range.value = '7'
  }
  summary.value = null
  loadSummary()
}

/** 一键批量置状态（只改本地，提交后落库）。 */
function markAll(status) {
  if (!items.value.length) return
  items.value.forEach((s) => {
    s.status = status
  })
  if (status === '出勤') {
    ElMessage.success('已设为全员出勤')
  } else {
    ElMessage.success('已设为全员缺勤，请点选到校学生')
  }
}

/** 提交点名：仅提交本班在籍学生的合法状态。 */
async function submit() {
  if (!classId.value) return ElMessage.warning('请先选择班级')
  if (!items.value.length) {
    // 区分「真没学生」与「没加载上」：切班/换日期失败时 items 已被清空（error=true），
    // 此时说「该班暂无在籍学生」是在说假话，老师会以为班里没学生而不是加载失败。
    return ElMessage.warning(
      error.value ? '名单加载失败，请先点上方的「重试」重新加载' : '该班暂无在籍学生'
    )
  }
  if (saving.value) return // 防重复点击（:loading 只是视觉，双击仍会触发两次）
  // 名单必须来自当前班级+日期：切班在途时提交会把上一个班的名单按新 class_id 写库
  if (checkinLoadedKey !== checkinKeyNow()) {
    return ElMessage.warning('名单还在加载，请稍候再提交')
  }
  const records = items.value
    .filter((s) => STATUS_LIST.includes(s.status))
    .map((s) => ({ student_id: s.student_id, status: s.status }))
  if (!records.length) return ElMessage.warning('请先设置学生状态')

  saving.value = true
  try {
    await attendanceApi.checkin({ class_id: classId.value, date: date.value, records })
    ElMessage.success('点名成功')
    // 点名会改变统计口径，让统计页签下次进入时重新取数
    statsLoadedKey = ''
  } catch (e) {
    // 全局拦截器已弹出后端错误详情，这里只解除 loading
  } finally {
    saving.value = false
  }
}

onMounted(loadClasses)
</script>

<style scoped>
/* el-tabs 自带 header 的下边距在该布局里偏大，与 toolbar 叠一起显得松散 */
.att-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

/* 刷新失败提示条（不引入全局样式，仅本页） */
.refresh-alert {
  margin-bottom: 12px;
}

.status-hint {
  font-size: 12px;
  color: #9ca3af;
  line-height: 1.5;
}

.rate-card {
  background: #f9fafb;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  margin-bottom: 16px;
}

.rate-num {
  font-size: 40px;
  font-weight: 700;
  line-height: 1.1;
}

.rate-label {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}

.rate-sub {
  font-size: 13px;
  color: #374151;
  margin-top: 8px;
}

.rate-range {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-cell {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px;
  text-align: center;
}

.stat-num {
  font-size: 24px;
  font-weight: 700;
}

.stat-label {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.trend-table {
  margin-top: 4px;
}

.trend-empty {
  padding: 32px 0;
  text-align: center;
  font-size: 13px;
  color: #9ca3af;
}

/* 窄屏：状态分布 4 列挤成一行会溢出，退化为 2 列 */
@media (max-width: 768px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .rate-num {
    font-size: 32px;
  }
}
</style>
