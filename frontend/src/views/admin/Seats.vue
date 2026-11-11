<template>
  <div>
    <div class="toolbar">
      <el-select
        v-model="classId"
        placeholder="选择班级"
        style="width: 200px"
        @change="onClassChange"
      >
        <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-input-number v-model="columns" :min="3" :max="8" />
      <span style="font-size: 13px; color: #6b7280">列数</span>
      <div class="spacer"></div>
      <el-button @click="sortByNo">按学号排序</el-button>
      <el-button @click="shuffle">随机排座</el-button>
      <el-button type="primary" :loading="saving" :disabled="saving || loading" @click="save"
        >保存布局</el-button
      >
    </div>

    <div class="page-card" v-loading="loading">
      <div v-if="!classId" class="empty-state empty-state--tall">请先选择班级</div>
      <div v-else-if="seats.length === 0" class="empty-state empty-state--tall">该班级暂无学生</div>
      <div v-else class="seat-grid" :style="{ gridTemplateColumns: `repeat(${columns}, 1fr)` }">
        <div
          v-for="(s, i) in seats"
          :key="s.id"
          class="seat"
          :class="{ selected: selectedIndex === i, male: s.gender === '男' }"
          @click="clickSeat(i)"
        >
          <div class="seat-no">{{ i + 1 }}</div>
          <div class="seat-name">{{ s.name }}</div>
        </div>
      </div>
      <p v-if="seats.length" style="margin-top: 12px; font-size: 12px; color: #9ca3af">
        提示：点击两个座位即可交换位置
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { studentApi, seatApi } from '../../api'

const classes = ref([])
const classId = ref(null)
const columns = ref(6)
const seats = ref([])
const selectedIndex = ref(null)
// 切换班级时加载座位/学生列表的在途标记；保存布局的在途标记（防重复提交）
const loading = ref(false)
const saving = ref(false)

/**
 * 「最后一次请求胜出」序号（与 `composables/useCrudList.js` 同款）。
 *
 * 切换班级会连发两次请求（先读已保存布局、再读学生名单），而 `api/request.js` 的
 * 并发去重 key 里含 url/params，两个班级的请求互不取消。没有序号保护时，
 * 先切 A（慢）、再切 B，A 的名单会最后落到 `seats` 上；此时点「保存布局」就是把
 * **B 班的 class_id 配上 A 班的学生**写库，直接覆盖掉 B 班已保存的座位表（RBT-101）。
 */
let loadSeq = 0

/**
 * 当前 `seats` 是从哪个班级加载出来的（`null` = 名单未就绪）。
 *
 * 与 `loadSeq` 互补：序号保证只有最新一次请求能写 `seats`，本字段在**保存前**再比对一次
 * 「这批名单是否还是当前班级的」—— 双保险，避免以后新增加载路径漏掉序号守卫时
 * 又把 A 班名单按 B 班写库（座位表被覆盖后无法从接口恢复）。
 */
const seatsClassId = ref(null)

onMounted(async () => {
  // 使用 studentApi.classrooms()：管理员看全部，教师只看自己负责的班级
  const res = await studentApi.classrooms()
  classes.value = res.items
})

async function onClassChange() {
  const my = ++loadSeq
  // 固定本次请求的目标班级：await 之间可能再切一次班级，不能读实时的 classId
  const targetClassId = classId.value
  selectedIndex.value = null
  // 名单尚未就绪，此期间禁止保存（切换过程中 seats 里还是上一个班的人）
  seatsClassId.value = null
  // 清空选择时无需请求，直接清空座位，避免用 null 班级去查接口
  if (!targetClassId) {
    seats.value = []
    return
  }
  loading.value = true
  try {
    // 尝试加载已保存布局
    const saved = await seatApi.get(targetClassId)
    if (my !== loadSeq) return
    columns.value = saved.columns || 6
    const students = await loadStudents(targetClassId)
    if (my !== loadSeq) return
    seats.value = arrangeStudents(students, saved.layout)
    seatsClassId.value = targetClassId
  } catch (e) {
    // 无已保存布局（后端返回空 / 404）或加载失败：回退为按学号的学生列表
    if (my !== loadSeq) return
    try {
      const students = await loadStudents(targetClassId)
      if (my !== loadSeq) return
      seats.value = students
      seatsClassId.value = targetClassId
    } catch (e2) {
      if (my !== loadSeq) return
      seats.value = []
      seatsClassId.value = null
    }
  } finally {
    // 只有最新一次请求才能结束 loading，否则旧请求会提前撤掉新请求的骨架
    if (my === loadSeq) loading.value = false
  }
}

/** 按已保存布局排列学生：布局里仍在本班的学生按原顺序在前，其余补在后面。 */
function arrangeStudents(students, layout) {
  const map = new Map(students.map((s) => [s.id, s]))
  const ordered = []
  const used = new Set()
  // 旧布局可能残留转班/退学学生的 id：`map.has` 过滤掉，不让幽灵座位占位
  for (const id of (Array.isArray(layout) ? layout : []).flat()) {
    if (map.has(id) && !used.has(id)) {
      ordered.push(map.get(id))
      used.add(id)
    }
  }
  for (const s of students) if (!used.has(s.id)) ordered.push(s)
  return ordered
}

/** 读指定班级的学生名单（显式传 id：不使用可能已被改掉的 `classId`） */
async function loadStudents(id) {
  const res = await studentApi.list({ class_id: id, page: 1, page_size: 9999 })
  return res.items
}

function clickSeat(i) {
  if (selectedIndex.value === null) {
    selectedIndex.value = i
  } else if (selectedIndex.value === i) {
    selectedIndex.value = null
  } else {
    const a = selectedIndex.value
    const tmp = seats.value[a]
    seats.value[a] = seats.value[i]
    seats.value[i] = tmp
    selectedIndex.value = null
  }
}

function shuffle() {
  for (let i = seats.value.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[seats.value[i], seats.value[j]] = [seats.value[j], seats.value[i]]
  }
}

function sortByNo() {
  seats.value = [...seats.value].sort((a, b) =>
    (a.student_no || '').localeCompare(b.student_no || '')
  )
}

async function save() {
  // 未选班级时不能提交：此前会带着 class_id=null 发请求，后端无法定位座位表
  if (!classId.value) {
    return ElMessage.warning('请先选择班级')
  }
  if (saving.value) return
  // 名单必须来自当前班级：切班请求还没回来时保存，会把上一个班的名单按当前 class_id
  // 写库，覆盖掉当前班已保存的座位表且不可恢复（RBT-101；后端 seats_service 亦已加
  // 学生归属校验，这里是第一道拦截，让用户看到「请稍候」而不是一个 400）
  if (seatsClassId.value !== classId.value) {
    return ElMessage.warning('班级名单还在加载，请稍候再保存')
  }
  saving.value = true
  try {
    const layout = seats.value.map((s) => s.id)
    await seatApi.save({ class_id: classId.value, layout: [layout], columns: columns.value })
    ElMessage.success('座位布局已保存')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.seat-grid {
  display: grid;
  gap: 12px;
}
.seat {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}
.seat:hover {
  border-color: #2563eb;
}
.seat.selected {
  border-color: #2563eb;
  background: #eff6ff;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.25);
}
.seat.male .seat-name {
  color: #2563eb;
}
.seat-no {
  font-size: 12px;
  color: #9ca3af;
}
.seat-name {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
  margin-top: 4px;
}
.empty-state--tall {
  padding: 60px 0;
}
</style>
