<template>
  <div>
    <div class="page-card" style="max-width: 640px">
      <h3 class="card-title">平台设置</h3>

      <div class="section-label">注册管控</div>
      <el-form label-width="140px">
        <el-form-item label="学生自助注册">
          <el-switch
            v-model="allowRegistration"
            :loading="saving"
            :disabled="loading"
            active-text="开放注册"
            inactive-text="关闭注册"
            @change="onChange"
          />
          <div class="hint">
            开启后学生可在登录页自助注册；关闭后注册入口将从学生登录页隐藏，学生无法注册。
          </div>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi } from '../../api'

// 平台级「学生自助注册」总开关（全局作用域，跨校生效）
const allowRegistration = ref(false)
const loading = ref(false)
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await adminApi.platformRegistration()
    allowRegistration.value = !!res.allow_registration
  } catch (e) {
    console.error('[PlatformSettings] 加载注册开关失败:', e)
  } finally {
    loading.value = false
  }
}

async function onChange(val) {
  saving.value = true
  try {
    await adminApi.setPlatformRegistration({ allow_registration: val })
    ElMessage.success(val ? '已开启学生自助注册' : '已关闭学生自助注册')
  } catch (e) {
    // 保存失败：回滚开关状态，避免界面与后端不一致
    allowRegistration.value = !val
    ElMessage.error('设置失败，请稍后重试')
    console.error('[PlatformSettings] 保存注册开关失败:', e)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.card-title {
  margin: 0 0 16px;
  color: #111827;
}

.section-label {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  margin: 0 0 12px;
}

.hint {
  font-size: 12px;
  color: #9ca3af;
  line-height: 1.6;
  margin-top: 6px;
}
</style>
