<template>
  <div>
    <div class="page-card" style="max-width: 640px">
      <h3 class="card-title">系统设置</h3>
      <el-form label-width="140px">
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
          <el-button type="warning" @click="upgrade">一键年级升级</el-button>
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

const schoolName = ref('')
const semester = ref('')

onMounted(async () => {
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
  await ElMessageBox.confirm('确定执行年级升级吗？', '提示', { type: 'warning' })
  const res = await adminApi.upgradeGrade()
  ElMessage.success(`已升级 ${res.upgraded} 个班级`)
}
</script>

<style scoped>
.card-title {
  margin: 0 0 16px;
  color: #111827;
}
</style>
