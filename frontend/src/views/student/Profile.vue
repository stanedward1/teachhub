<template>
  <div>
    <h2 class="page-title">个人资料</h2>
    <p class="page-subtitle">管理你的基本信息、头像与密码</p>

    <div class="page-card" style="max-width: 520px">
      <!-- 头像区域 -->
      <div style="text-align: center; margin-bottom: 24px">
        <el-upload
          :show-file-list="false"
          :before-upload="beforeAvatarUpload"
          :http-request="handleAvatarUpload"
          accept=".jpg,.jpeg,.png,.gif,.webp"
        >
          <el-avatar :size="80" :src="avatarUrl" class="avatar-upload">
            {{ user?.name?.[0] }}
          </el-avatar>
          <div
            style="margin-top: 8px; color: var(--text-tertiary); font-size: 12px; cursor: pointer"
          >
            点击更换头像
          </div>
        </el-upload>
        <div style="color: var(--text-tertiary); font-size: 11px; margin-top: 4px">
          支持 JPG/PNG/GIF/WebP，不超过 2MB
        </div>
      </div>

      <el-form label-width="90px">
        <el-form-item label="姓名">
          <el-input :model-value="user?.name" disabled />
        </el-form-item>
        <el-form-item label="学号">
          <el-input :model-value="user?.username" disabled />
        </el-form-item>
        <el-form-item label="班级">
          <el-input :model-value="user?.class_name || '未分班'" disabled />
        </el-form-item>
      </el-form>
      <el-divider>修改密码</el-divider>
      <el-form label-width="90px">
        <el-form-item label="原密码">
          <el-input v-model="pwd.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwd.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="changePwd">保存</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { authApi } from '../../api'
import { getUser, setAuth, getToken } from '../../utils/auth'

const user = computed(() => getUser())
// 头像展示的响应式来源：getUser() 只读 localStorage、不具响应性，
// 更换头像后必须靠本地 ref 立即刷新界面（原 computed 依赖不到任何响应式源、永久缓存）
const avatarSrc = ref('')
const avatarUrl = computed(() => avatarSrc.value || user.value?.avatar || '')
const pwd = reactive({ old_password: '', new_password: '' })
const loading = ref(false)
const avatarLoading = ref(false)

onMounted(() => {
  avatarSrc.value = getUser()?.avatar || ''
})

function beforeAvatarUpload(file) {
  const allowed = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  if (!allowed.includes(file.type)) {
    ElMessage.error('仅支持 JPG/PNG/GIF/WebP 格式的图片')
    return false
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.error('头像文件不能超过 2MB')
    return false
  }
  return true
}

async function handleAvatarUpload(options) {
  avatarLoading.value = true
  try {
    const fd = new FormData()
    fd.append('file', options.file)
    const res = await authApi.uploadAvatar(fd)
    // 更新本地用户信息中的头像
    const current = getUser()
    if (current) {
      current.avatar = res.avatar
      const token = getToken()
      if (token) {
        setAuth(token, current)
      }
    }
    if (res.avatar) avatarSrc.value = res.avatar
    ElMessage.success('头像更新成功')
  } catch (e) {
  } finally {
    avatarLoading.value = false
  }
}

async function changePwd() {
  if (pwd.new_password.length < 6) return ElMessage.warning('新密码至少 6 位')
  loading.value = true
  try {
    await authApi.changePassword(pwd)
    ElMessage.success('密码修改成功')
    pwd.old_password = ''
    pwd.new_password = ''
  } catch (e) {
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.avatar-upload {
  cursor: pointer;
  transition: opacity 0.2s;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  font-weight: 700;
  font-size: 28px;
}
.avatar-upload:hover {
  opacity: 0.8;
}
</style>
