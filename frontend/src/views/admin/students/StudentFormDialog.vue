<template>
  <el-dialog
    :model-value="modelValue"
    :title="student ? '编辑学生' : '添加学生'"
    width="560px"
    @update:model-value="(v) => emit('update:modelValue', v)"
  >
    <el-form label-width="90px">
      <el-form-item label="学号" required><el-input v-model="form.student_no" /></el-form-item>
      <el-form-item label="姓名" required><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="性别">
        <el-radio-group v-model="form.gender"
          ><el-radio value="男">男</el-radio><el-radio value="女">女</el-radio></el-radio-group
        >
      </el-form-item>
      <el-form-item label="班级">
        <el-select v-model="form.class_id" clearable style="width: 100%">
          <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="专业"><el-input v-model="form.major" /></el-form-item>
      <el-form-item label="出生日期"
        ><el-input v-model="form.birth_date" placeholder="如 2008-05-12"
      /></el-form-item>
      <el-form-item label="家长姓名"><el-input v-model="form.parent_name" /></el-form-item>
      <el-form-item label="家长电话"><el-input v-model="form.parent_phone" /></el-form-item>
      <el-form-item label="学生类型">
        <el-radio-group v-model="form.student_type">
          <el-radio value="day">通学生</el-radio><el-radio value="boarding">寄宿生</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="退学">
        <el-switch v-model="form.is_dropped_out" active-text="已退学" inactive-text="在籍" />
        <div
          v-if="form.is_dropped_out"
          style="color: #e6a23c; font-size: 12px; line-height: 1.5; margin-top: 4px"
        >
          标记退学后，教师与管理员将无法再对该生进行成绩、考勤、积分等各项操作。
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
/**
 * 学生「添加 / 编辑」弹窗。
 *
 * 从 Students.vue 原样搬出，保持表单字段、label-width、宽度与提示文案不变。
 * 通过 `student` prop 区分新增（null）与编辑：新增用固定初值 + 当前筛选班级，
 * 编辑用 Object.assign 把整行（含 id/avatar/class_name 等额外键）带入表单，
 * 保存时原样提交给后端，保留原有语义。
 */
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { studentApi } from '../../../api'

/** 表单固定初值（与原组件完全一致）。 */
const DEFAULTS = {
  student_no: '',
  name: '',
  gender: '男',
  class_id: null,
  major: '',
  birth_date: '',
  parent_name: '',
  parent_phone: '',
  student_type: 'day',
  is_dropped_out: false,
}

const props = defineProps({
  /** 弹窗显隐（v-model） */
  modelValue: { type: Boolean, default: false },
  /** 班级下拉数据 */
  classes: { type: Array, default: () => [] },
  /** 待编辑学生；为 null 表示新增 */
  student: { type: Object, default: null },
  /** 新增时的默认班级（当前筛选班级）；el-select 清空时为 ''，故同时接受 String */
  defaultClassId: { type: [Number, String], default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const saving = ref(false)
const form = reactive({ ...DEFAULTS })

// 打开弹窗时按 student 初始化表单（等价于原 openCreate/openEdit 先初始化再打开）。
watch(
  () => props.modelValue,
  (v) => {
    if (v) init()
  }
)

function init() {
  if (props.student) {
    // 保留整行语义：额外键（id / avatar / class_name 等）一并带入并提交。
    Object.assign(form, DEFAULTS, props.student)
  } else {
    Object.assign(form, DEFAULTS, { class_id: props.defaultClassId })
  }
}

async function save() {
  if (!form.name || !form.student_no) return ElMessage.warning('请填写姓名和学号')
  saving.value = true
  try {
    if (props.student) await studentApi.update(props.student.id, form)
    else await studentApi.create(form)
    ElMessage.success('保存成功')
    emit('update:modelValue', false)
    emit('saved')
  } catch (e) {
  } finally {
    saving.value = false
  }
}
</script>
