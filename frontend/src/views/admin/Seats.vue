<template>
  <div>
    <div class="toolbar">
      <el-select v-model="classId" placeholder="选择班级" style="width: 200px" @change="onClassChange">
        <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-input-number v-model="columns" :min="3" :max="8" />
      <span style="font-size: 13px; color: #6b7280">列数</span>
      <div class="spacer"></div>
      <el-button @click="sortByNo">按学号排序</el-button>
      <el-button @click="shuffle">随机排座</el-button>
      <el-button type="primary" :loading="saving" :disabled="saving" @click="save"
        >保存布局</el-button
      >
    </div>

    <div class="page-card" v-loading="loading">
      <div v-if="!classId" class="empty">请先选择班级</div>
      <div v-else-if="seats.length === 0" class="empty">该班级暂无学生</div>
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

onMounted(async () => {
  // 使用 studentApi.classrooms()：管理员看全部，教师只看自己负责的班级
  const res = await studentApi.classrooms()
  classes.value = res.items
})

async function onClassChange() {
  selectedIndex.value = null
  // 清空选择时无需请求，直接清空座位，避免用 null 班级去查接口
  if (!classId.value) {
    seats.value = []
    return
  }
  loading.value = true
  try {
    // 尝试加载已保存布局
    const saved = await seatApi.get(classId.value)
    columns.value = saved.columns || 6
    const students = await loadStudents()
    const map = new Map(students.map((s) => [s.id, s]))
    const layout = saved.layout.flat()
    const ordered = []
    const used = new Set()
    for (const id of layout) {
      if (map.has(id) && !used.has(id)) {
        ordered.push(map.get(id))
        used.add(id)
      }
    }
    for (const s of students) if (!used.has(s.id)) ordered.push(s)
    seats.value = ordered
  } catch (e) {
    // 无已保存布局（后端返回空 / 404）或加载失败：回退为按学号的学生列表
    try {
      seats.value = await loadStudents()
    } catch (e2) {
      seats.value = []
    }
  } finally {
    loading.value = false
  }
}

async function loadStudents() {
  const res = await studentApi.list({ class_id: classId.value, page: 1, page_size: 9999 })
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
  seats.value = [...seats.value].sort((a, b) => (a.student_no || '').localeCompare(b.student_no || ''))
}

async function save() {
  // 未选班级时不能提交：此前会带着 class_id=null 发请求，后端无法定位座位表
  if (!classId.value) {
    return ElMessage.warning('请先选择班级')
  }
  if (saving.value) return
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
.empty {
  text-align: center;
  color: #9ca3af;
  padding: 60px 0;
}
</style>
