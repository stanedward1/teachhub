<template>
  <div>
    <div class="page-card" style="max-width: 640px">
      <h3 class="card-title">系统设置</h3>
      <!-- 平台超管在本页没有「校内作用域」：设置表按 (school_id, key) 隔离，超管的
           school_id 为 NULL，保存会落到全局行 → 对任何校内管理员都不可见（等于改了没用）。
           后端已对此返回 400，这里直接把表单换掉，避免用户白填。 -->
      <el-alert
        v-if="isPlatformUser"
        type="info"
        :closable="false"
        show-icon
        title="平台级配置请前往「平台设置」"
        description="本页维护的是各校的校内设置（学校名称 / 当前学期），平台超管没有校内作用域。"
      />
      <el-form v-else label-width="140px">
        <el-form-item label="学校名称">
          <el-input v-model="schoolName" />
        </el-form-item>
        <el-form-item label="当前学期">
          <el-input v-model="semester" placeholder="如 2025-2026 学年第一学期" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveSettings">保存设置</el-button>
        </el-form-item>
      </el-form>
      <el-divider />
      <el-form label-width="140px">
        <el-form-item label="年级升级">
          <el-button type="warning" :loading="upgrading" :disabled="upgrading" @click="upgrade"
            >一键年级升级</el-button
          >
          <div style="font-size: 12px; color: #9ca3af; margin-top: 6px">
            将所有班级年级升一级（一年级→二年级，以此类推）
          </div>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '../../api'
import { isPlatformAdmin } from '../../utils/auth'

const schoolName = ref('')
const semester = ref('')
// 平台超管：本页的校内设置表单对其隐藏（见模板注释与后端 set_setting 的 400 守卫）
const isPlatformUser = isPlatformAdmin()
// 年级升级忙碌标记：升级是不可逆的破坏性操作，双击会连升两级
// 从「打开确认框」那一刻即置位，覆盖「确认框未决」与「升级请求在途」两个阶段
const upgrading = ref(false)

onMounted(async () => {
  if (isPlatformUser) return // 表单不可见，不必请求
  try {
    const res = await adminApi.settings()
    const map = {}
    res.items.forEach((s) => (map[s.key] = s.value))
    schoolName.value = map.school_name || ''
    semester.value = map.semester || ''
  } catch (e) {
    console.error('[Settings] 加载设置失败:', e)
  }
})

async function saveSettings() {
  await adminApi.setSetting('school_name', schoolName.value)
  await adminApi.setSetting('semester', semester.value)
  ElMessage.success('设置已保存')
}

async function upgrade() {
  // 重入护栏：确认框未决期间与升级请求在途期间，都忽略重复触发，避免连升两级
  if (upgrading.value) return
  // 先置位忙碌标记再去 await 确认框，堵住「确认框未决期间双击开两个框」的窗口
  upgrading.value = true
  try {
    try {
      await ElMessageBox.confirm('确定执行年级升级吗？', '提示', { type: 'warning' })
    } catch (e) {
      return // 用户取消确认：静默返回，保持既有「取消不弹错误提示」的行为
    }
    const res = await adminApi.upgradeGrade()
    ElMessage.success(`已升级 ${res.upgraded} 个班级`)
  } finally {
    // 成功 / 用户取消 / 接口异常 三条路径都复位标记，避免按钮被永久 loading/disabled
    upgrading.value = false
  }
}
</script>

<style scoped>
.card-title {
  margin: 0 0 16px;
  color: #111827;
}
</style>
