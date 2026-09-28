<template>
  <el-dialog
    :model-value="modelValue"
    title="批量修改学生密码"
    width="480px"
    @update:model-value="(v) => emit('update:modelValue', v)"
  >
    <el-form label-width="90px">
      <el-form-item label="已选学生">
        <span style="font-weight: 500">{{ students.length }} 人</span>
        <div v-if="students.length" style="color: #909399; font-size: 12px; line-height: 1.6">
          {{ namesPreview }}
        </div>
      </el-form-item>
      <el-form-item label="新密码">
        <el-input
          v-model="form.password"
          placeholder="留空则重置为默认密码 123456"
          show-password
          style="width: 240px"
        />
        <div style="color: #909399; font-size: 12px; line-height: 1.6; margin-top: 4px">
          弱密码（不满足 8 位且含字母数字）会标记为「需修改」，学生下次登录时会被要求改密。
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">确定修改</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
/**
 * 学生「批量修改密码」弹窗。
 *
 * 由 Students.vue 的表格多选触发：把选中的学生档案 id 列表交给后端
 * `PUT /api/students/password/batch`。新密码留空 = 重置为默认密码 123456，
 * 与单条改密（StudentPasswordDialog）的语义保持一致。
 *
 * 后端对「不存在 / 无权限 / 已退学」的目标会**跳过**并回传 `failed`，
 * 因此这里按「成功 n 人 / 失败 m 人」分别提示，而不是笼统报成功或失败。
 */
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { studentApi } from '../../../api'

const props = defineProps({
  /** 弹窗显隐（v-model） */
  modelValue: { type: Boolean, default: false },
  /** 目标学生行列表（至少 1 条；含 id / name / student_no） */
  students: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const saving = ref(false)
const form = reactive({ password: '' })

// 打开弹窗时清空输入框（避免上一次残留；沿用单条改密弹窗的行为）
watch(
  () => props.modelValue,
  (v) => {
    if (v) form.password = ''
  }
)

// 最多展示前 8 个姓名，超出用「等 N 人」收口，避免弹窗被撑爆
const namesPreview = computed(() => {
  const names = props.students.slice(0, 8).map((s) => s.name)
  const more = props.students.length - names.length
  return more > 0 ? `${names.join('、')} 等 ${props.students.length} 人` : names.join('、')
})

async function submit() {
  const ids = props.students.map((s) => s.id)
  if (!ids.length) return ElMessage.warning('请先选择学生')

  // 新密码留空 ⇒ 交给后端重置为默认 123456；填了则做最小长度校验
  const pwd = form.password.trim()
  if (pwd && pwd.length < 6) return ElMessage.warning('密码长度至少 6 位')

  saving.value = true
  try {
    const res = await studentApi.batchResetPassword({
      student_ids: ids,
      ...(pwd ? { password: pwd } : {}),
    })
    const updated = res?.updated ?? 0
    const failed = res?.failed ?? []
    if (failed.length) {
      // 部分失败：把失败原因汇总给用户，便于逐个处理
      const reasons = [...new Set(failed.map((f) => f.reason))].join('；')
      ElMessage.warning(`成功修改 ${updated} 人，${failed.length} 人未修改：${reasons}`)
    } else {
      ElMessage.success(
        res?.updated ? `已修改 ${updated} 名学生的密码` : '已批量重置为默认密码 123456'
      )
    }
    emit('update:modelValue', false)
    emit('saved')
  } catch (e) {
    // 错误提示由 request 拦截器统一处理
  } finally {
    saving.value = false
  }
}
</script>
