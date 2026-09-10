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
      @update:model-value="onClassChange"
    >
      <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
    </el-select>

    <!-- 学生选择 -->
    <el-select
      :model-value="modelValue"
      filterable
      clearable
      :placeholder="placeholder"
      style="width: 100%"
      @update:model-value="$emit('update:modelValue', $event)"
    >
      <el-option v-for="s in students" :key="s.id" :label="`${s.name}（${s.student_no}）`" :value="s.id" />
    </el-select>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { studentApi } from '../api'

const props = defineProps({
  modelValue: { type: [Number, String], default: null },
  classId: { type: [Number, String], default: null },
  placeholder: { type: String, default: '选择学生' },
  // 是否显示班级筛选：true 则先选班级再选学生
  showClassFilter: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'update:classId'])

const classes = ref([])
const students = ref([])
// 本地班级状态：不依赖异步 props，保证选班级后立即按新班级加载学生
const localClassId = ref(props.classId)

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

// 父组件外部设置 classId（v-model:classId 绑定时）→ 同步本地状态并重载学生
watch(() => props.classId, (v) => {
  localClassId.value = v
  loadStudents(v)
})

// 监听 showClassFilter 变化（动态切换时重新加载）
watch(() => props.showClassFilter, () => loadStudents(localClassId.value))

// 用户选择班级：更新本地状态 + 通知父组件 + 立即按新班级加载学生
function onClassChange(val) {
  localClassId.value = val
  emit('update:classId', val)
  // 班级变了，清空已选学生，避免残留上一班级的学生 ID
  if (props.modelValue) emit('update:modelValue', null)
  loadStudents(val)
}

async function loadStudents(classIdArg) {
  // classIdArg 优先（用户刚选的班级），否则用本地状态
  const cid = classIdArg !== undefined ? classIdArg : localClassId.value
  const params = { page: 1, page_size: 9999, dropped_out: 'false' }
  if (props.showClassFilter && cid) {
    params.class_id = cid
  }
  try {
    const res = await studentApi.list(params)
    students.value = res.items || []
  } catch (e) {
    students.value = []
  }
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
