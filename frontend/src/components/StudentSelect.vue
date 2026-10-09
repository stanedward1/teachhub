<template>
  <div class="student-select-wrapper" :class="{ 'has-class-filter': showClassFilter }">
    <!-- 班级选择（可选）：先选班级，再在班级内选学生 -->
    <el-select
      v-if="showClassFilter"
      :model-value="localClassId"
      filterable
      clearable
      placeholder="先选班级"
      style="width: 100%"
      :disabled="disabled"
      @update:model-value="onClassChange"
    >
      <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
    </el-select>

    <!-- 学生选择：remote 远程搜索，避免一次性拉全量学生 -->
    <el-select
      :model-value="modelValue"
      filterable
      remote
      :remote-method="onRemoteSearch"
      :loading="loading"
      clearable
      :placeholder="placeholder"
      style="width: 100%"
      :disabled="disabled"
      @update:model-value="$emit('update:modelValue', $event)"
      @visible-change="onVisibleChange"
    >
      <el-option
        v-for="s in mergedOptions"
        :key="s.id"
        :label="`${s.name}（${s.student_no}）`"
        :value="s.id"
      />
    </el-select>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { studentApi } from '../api'

// 远程搜索页大小：打开下拉拉前 50 条，输入关键字走 keyword 搜索
const PAGE_SIZE = 50
const SEARCH_DEBOUNCE_MS = 300

const props = defineProps({
  modelValue: { type: [Number, String], default: null },
  classId: { type: [Number, String], default: null },
  placeholder: { type: String, default: '选择学生' },
  // 是否显示班级筛选：true 则先选班级再选学生
  showClassFilter: { type: Boolean, default: false },
  // 是否禁用：编辑态等场景下屏蔽交互（默认 false，保证存量调用方行为不变）
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'update:classId'])

const classes = ref([])
const students = ref([])
const loading = ref(false)
// 本地班级状态：不依赖异步 props，保证选班级后立即按新班级加载学生
const localClassId = ref(props.classId)
// 回显缓存：编辑场景下已选学生可能不在前 50 条内，单独缓存保证 label 正常显示
const selectedCache = ref([])
const resolvedIds = new Set()
let searchTimer = null

// 展示选项 = 回显缓存 + 当前搜索结果（按 id 去重，缓存优先）
const mergedOptions = computed(() => {
  const map = new Map()
  for (const s of selectedCache.value) map.set(s.id, s)
  for (const s of students.value) map.set(s.id, s)
  return [...map.values()]
})

function buildParams(keyword = '', pageSize = PAGE_SIZE) {
  const params = { page: 1, page_size: pageSize, dropped_out: 'false' }
  if (props.showClassFilter && localClassId.value) {
    params.class_id = localClassId.value
  }
  if (keyword) {
    params.keyword = keyword
  }
  return params
}

async function fetchStudents(params) {
  loading.value = true
  try {
    const res = await studentApi.list(params)
    return res.items || []
  } catch (e) {
    return []
  } finally {
    loading.value = false
  }
}

// 加载默认列表（打开下拉 / 切换班级）：前 PAGE_SIZE 条
async function loadStudents(classIdArg) {
  // classIdArg 优先（用户刚选的班级），否则用本地状态
  const cid = classIdArg !== undefined ? classIdArg : localClassId.value
  localClassId.value = cid
  students.value = await fetchStudents(buildParams())
  resolveSelected()
}

// el-select remote 模式：输入关键字时触发，300ms 防抖后搜索
function onRemoteSearch(query) {
  const kw = (query || '').trim()
  if (!kw) {
    // 清空关键字 → 回到默认前 50 条
    if (searchTimer) clearTimeout(searchTimer)
    loadStudents()
    return
  }
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(async () => {
    students.value = await fetchStudents(buildParams(kw))
  }, SEARCH_DEBOUNCE_MS)
}

// 下拉打开时刷新默认列表（关闭时不动，避免清掉用户刚选中的选项上下文）
function onVisibleChange(visible) {
  if (visible) loadStudents()
}

// 回显兜底：modelValue 已有值但不在当前选项 / 缓存中时，拉一次全量定位该生。
// 仅编辑回显场景发生（后端无按 id 查详情的端点），已定位过的 id 不再重复拉取。
async function resolveSelected() {
  const id = props.modelValue
  if (!id || resolvedIds.has(id)) return
  const hit =
    students.value.find((s) => s.id === id) || selectedCache.value.find((s) => s.id === id)
  if (hit) {
    resolvedIds.add(id)
    return
  }
  const all = await fetchStudents(buildParams('', 9999))
  const found = all.find((s) => s.id === id)
  if (found) {
    resolvedIds.add(id)
    selectedCache.value = [...selectedCache.value.filter((s) => s.id !== id), found]
  }
}

onMounted(async () => {
  // 加载班级列表（后端已按教师角色过滤；仅返回未毕业班级，避免对毕业班级学生操作）
  try {
    const res = await studentApi.classrooms({ graduated: 'false' })
    classes.value = res.items || []
  } catch (e) {
    console.error('[StudentSelect] 加载班级列表失败:', e)
  }
  loadStudents(localClassId.value)
})

onBeforeUnmount(() => {
  if (searchTimer) clearTimeout(searchTimer)
})

// 父组件外部设置 classId（v-model:classId 绑定时）→ 同步本地状态并重载学生
watch(
  () => props.classId,
  (v) => {
    localClassId.value = v
    loadStudents(v)
  }
)

// 监听 showClassFilter 变化（动态切换时重新加载）
watch(
  () => props.showClassFilter,
  () => loadStudents(localClassId.value)
)

// 父组件外部设置/回显学生 id（编辑场景）→ 确保该生 label 可显示
watch(
  () => props.modelValue,
  () => resolveSelected()
)

// 用户选择班级：更新本地状态 + 通知父组件 + 立即按新班级加载学生
function onClassChange(val) {
  localClassId.value = val
  emit('update:classId', val)
  // 班级变了，清空已选学生，避免残留上一班级的学生 ID
  if (props.modelValue) emit('update:modelValue', null)
  loadStudents(val)
}
</script>

<style scoped>
.student-select-wrapper {
  display: flex;
  gap: 8px;
  align-items: center;
}
.student-select-wrapper.has-class-filter :deep(.el-select:first-child) {
  flex: 0 0 45%;
}
.student-select-wrapper.has-class-filter :deep(.el-select:last-child) {
  flex: 1;
}
</style>
