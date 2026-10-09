<template>
  <el-dialog v-model="visible" :title="score ? '编辑成绩' : '录入成绩'" width="440px">
    <el-form label-width="80px">
      <el-form-item label="学生" required
        ><StudentSelect v-model="form.student_id" show-class-filter
      /></el-form-item>
      <el-form-item label="科目" required><el-input v-model="form.subject" /></el-form-item>
      <el-form-item label="成绩" required
        ><el-input-number v-model="form.score" :min="0" :max="100"
      /></el-form-item>
      <el-form-item label="考试名称"><el-input v-model="form.exam_name" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
/**
 * 成绩录入 / 编辑弹窗。
 *
 * 从 Scores.vue 原样搬迁而来（模板 99-110 行 + dialog/editing/saving/form 状态
 * 与 openCreate/openEdit/save 逻辑），仅把 v-model / 方法调用改为 props/emits 链路。
 * 对外行为（校验文案、接口调用、提示文案、关闭时机、字段透传语义）保持完全等价。
 */
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import StudentSelect from '../../../components/StudentSelect.vue'
import { scoreApi } from '../../../api'

const props = defineProps({
  /** 弹窗显隐（v-model） */
  modelValue: { type: Boolean, default: false },
  /** 待编辑的成绩行；为 null 表示新增 */
  score: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const saving = ref(false)
// 表单默认值：新增时使用；编辑时先铺默认值再被行数据的**已声明字段**覆盖，
// 避免把 row 上的额外键（id / student_name / student_no 等）注入 reactive 并提交。
const DEFAULTS = { student_id: null, subject: '', score: 0, exam_name: '' }
const form = reactive({ ...DEFAULTS })

// 打开弹窗时初始化表单（原父组件在 openCreate/openEdit 中同步完成）
watch(
  () => props.modelValue,
  (v) => {
    if (v) init()
  }
)

function init() {
  if (props.score) {
    // 只拷表单声明的字段
    const picked = {}
    for (const key of Object.keys(DEFAULTS)) {
      if (props.score[key] !== undefined) picked[key] = props.score[key]
    }
    Object.assign(form, DEFAULTS, picked)
  } else {
    Object.assign(form, DEFAULTS)
  }
}

async function save() {
  if (!form.student_id || !form.subject) return ElMessage.warning('请选择学生并填写科目')
  saving.value = true
  try {
    // 显式构造载荷：只提交表单声明的字段
    const payload = {}
    for (const key of Object.keys(DEFAULTS)) payload[key] = form[key]
    if (props.score) await scoreApi.update(props.score.id, payload)
    else await scoreApi.create(payload)
    ElMessage.success('保存成功')
    visible.value = false
    emit('saved')
  } catch (e) {
  } finally {
    saving.value = false
  }
}
</script>
