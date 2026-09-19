<template>
  <div class="cp-wrap">
    <div class="cp-card">
      <div class="brand">
        <div class="brand-mark">T</div>
        <div>
          <h2>修改密码</h2>
          <p v-if="isFirst">首次登录或密码已被重置，请先设置新密码</p>
          <p v-else>定期修改密码，保护账号安全</p>
        </div>
      </div>

      <el-form label-position="top" @submit.prevent="doChange">
        <el-form-item label="原密码" required>
          <el-input
            v-model="form.old_password"
            type="password"
            show-password
            placeholder="请输入原密码"
          />
        </el-form-item>
        <el-form-item label="新密码" required>
          <el-input
            v-model="form.new_password"
            type="password"
            show-password
            placeholder="至少8位，含字母和数字"
          />
        </el-form-item>
        <el-form-item label="确认新密码" required>
          <el-input
            v-model="form.confirm"
            type="password"
            show-password
            placeholder="再次输入新密码"
          />
        </el-form-item>

        <div class="strength-hint">
          <div class="hint-title">密码强度要求：</div>
          <div class="hint-item" :class="{ ok: form.new_password.length >= 8 }">✓ 至少 8 位</div>
          <div class="hint-item" :class="{ ok: /[a-zA-Z]/.test(form.new_password) }">
            ✓ 包含字母
          </div>
          <div class="hint-item" :class="{ ok: /\d/.test(form.new_password) }">✓ 包含数字</div>
          <div class="hint-item" :class="{ ok: new Set(form.new_password).size >= 2 }">
            ✓ 不能全为相同字符
          </div>
        </div>

        <el-button
          type="primary"
          style="width: 100%; margin-top: 8px"
          :loading="loading"
          @click="doChange"
        >
          确认修改
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '../../api'
import { useLogout } from '../../composables/useLogout'

const route = useRoute()
const logout = useLogout()
const isFirst = computed(() => route.query.first === '1')
const loading = ref(false)
const form = reactive({ old_password: '', new_password: '', confirm: '' })

async function doChange() {
  if (!form.old_password || !form.new_password || !form.confirm) {
    return ElMessage.warning('请填写完整')
  }
  if (form.new_password !== form.confirm) {
    return ElMessage.warning('两次输入的新密码不一致')
  }
  if (
    form.new_password.length < 8 ||
    !/[a-zA-Z]/.test(form.new_password) ||
    !/\d/.test(form.new_password)
  ) {
    return ElMessage.warning('密码需至少8位，包含字母和数字')
  }
  loading.value = true
  try {
    await authApi.changePassword({
      old_password: form.old_password,
      new_password: form.new_password,
    })
    ElMessage.success('密码修改成功，请重新登录')
    // 改密后撤销服务端刷新令牌，再清理本地登录态
    logout('/admin/login')
  } catch (e) {
    // 后端错误信息已由 axios 拦截器提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.cp-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #2563eb 100%);
  padding: 20px;
}
.cp-card {
  width: 420px;
  max-width: 100%;
  background: #fff;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}
.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 24px;
}
.brand-mark {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  font-size: 24px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.brand h2 {
  margin: 0;
  font-size: 20px;
}
.brand p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 13px;
}
.strength-hint {
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 8px;
  font-size: 12px;
}
.hint-title {
  font-weight: 500;
  color: #374151;
  margin-bottom: 4px;
}
.hint-item {
  color: #9ca3af;
}
.hint-item.ok {
  color: #16a34a;
}
</style>
