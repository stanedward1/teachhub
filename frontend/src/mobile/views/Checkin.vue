<template>
  <div class="m-checkin">
    <van-dropdown-menu>
      <van-dropdown-item v-model="classId" :options="classOptions" @change="load" />
    </van-dropdown-menu>

    <van-cell-group inset style="margin-top: 8px">
      <van-field :model-value="date" readonly is-link label="日期" placeholder="选择日期" @click="showCalendar = true" />
      <van-cell title="出勤率统计" is-link icon="bar-chart-o" @click="$router.push('/m/attendance-stats')" />
    </van-cell-group>

    <!-- 快捷操作：默认全员出勤，只标异常 -->
    <div class="m-quick" v-if="students.length">
      <van-button size="small" type="primary" plain icon="completed" @click="markAllPresent">全员出勤</van-button>
      <van-button size="small" type="warning" plain icon="refresh" @click="markAllAbsent">全员缺勤</van-button>
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
    <van-empty v-if="!loading && !students.length" description="请先选择班级" />

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
import { ref, computed, onMounted } from 'vue'
import { showToast, showSuccessToast } from 'vant'
import { attendanceApi, studentApi } from '../../api'

const classId = ref(null)
const classOptions = ref([])
const date = ref(fmt(new Date()))
const students = ref([])
const loading = ref(false)
const saving = ref(false)
const showCalendar = ref(false)

const showAction = ref(false)
const currentStudent = ref(null)
const statusActions = [
  { name: '出勤' },
  { name: '缺勤' },
  { name: '请假' },
  { name: '迟到' }
]

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

function fmt(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

async function loadClasses() {
  try {
    const res = await studentApi.classrooms({ graduated: 'false' })
    classOptions.value = (res.items || []).map((c) => ({ text: c.name, value: c.id }))
    if (classOptions.value.length && !classId.value) {
      classId.value = classOptions.value[0].value
      await load()
    }
  } catch (e) {
  }
}

async function load() {
  if (!classId.value) return
  loading.value = true
  try {
    const res = await attendanceApi.list({ class_id: classId.value, date: date.value })
    students.value = res.items || []
  } catch (e) {
  } finally {
    loading.value = false
  }
}

// 一键全员出勤
function markAllPresent() {
  students.value.forEach((s) => { s.status = '出勤' })
  showToast('已设为全员出勤')
}

// 一键全员缺勤（用于反选：先全缺勤，再把到校的标成出勤）
function markAllAbsent() {
  students.value.forEach((s) => { s.status = '缺勤' })
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

function onDateConfirm(d) {
  date.value = fmt(d)
  showCalendar.value = false
  load()
}

async function submit() {
  if (!students.value.length) return showToast('暂无学生')
  saving.value = true
  try {
    const records = students.value.map((s) => ({ student_id: s.student_id, status: s.status }))
    await attendanceApi.checkin({ class_id: classId.value, date: date.value, records })
    showSuccessToast('点名成功')
  } catch (e) {
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
