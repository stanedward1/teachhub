<template>
  <el-dialog
    :model-value="modelValue"
    title="学生密码管理"
    width="440px"
    @update:model-value="(v) => emit('update:modelValue', v)"
  >
    <el-form label-width="80px">
      <el-form-item label="学生">
        <span style="font-weight: 500">{{ student?.name }}（{{ student?.student_no }}）</span>
      </el-form-item>
      <el-form-item label="重置密码">
        <el-button type="warning" @click="resetPassword">重置为默认密码（123456）</el-button>
      </el-form-item>
      <el-divider />
      <el-form-item label="修改密码">
        <el-input
          v-model="form.password"
          placeholder="请输入新密码"
          show-password
          style="width: 220px"
        />
        <el-button type="primary" style="margin-left: 8px" :loading="saving" @click="modifyPassword"
          >确定修改</el-button
        >
      </el-form-item>
    </el-form>
  </el-dialog>
</template>

<script setup>
/**
 * 学生密码管理弹窗（重置为默认密码 / 手动修改）。
 *
 * 从 Students.vue 原样搬出，宽度 440px、label-width 80px、分隔线与文案不变。
 * 每次打开弹窗清空输入的密码（等价于原 openPassword 行为）。
 */
import { ref, reactive, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { studentApi } from '../../../api'

const props = defineProps({
  /** 弹窗显隐（v-model） */
  modelValue: { type: Boolean, default: false },
  /** 目标学生 */
  student: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue'])

const saving = ref(false)
const form = reactive({ password: '' })

// 打开弹窗时清空密码输入框。
watch(
  () => props.modelValue,
  (v) => {
    if (v) form.password = ''
  }
)

async function resetPassword() {
  try {
    await ElMessageBox.confirm(
      `确定将「${props.student?.name}」的密码重置为默认密码（123456）吗？`,
      '确认重置',
      { type: 'warning' }
    )
  } catch {
    return
  }
  saving.value = true
  try {
    await studentApi.resetPassword(props.student.id, { password: '123456' })
    ElMessage.success('密码已重置为 123456')
    emit('update:modelValue', false)
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function modifyPassword() {
  if (!form.password) return ElMessage.warning('请输入新密码')
  if (form.password.length < 6) return ElMessage.warning('密码长度至少6位')
  saving.value = true
  try {
    await studentApi.resetPassword(props.student.id, { password: form.password })
    ElMessage.success('密码修改成功')
    emit('update:modelValue', false)
  } catch (e) {
  } finally {
    saving.value = false
  }
}
</script>
