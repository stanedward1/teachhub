<template>
  <div class="m-login">
    <div class="m-login-header">
      <div class="m-logo">T</div>
      <h1>TechHub</h1>
      <p>教师 / 管理员移动端</p>
    </div>
    <van-form @submit="doLogin">
      <van-cell-group inset>
        <van-field
          v-model="form.username"
          name="username"
          label="账号"
          placeholder="用户名"
          clearable
        />
        <van-field
          v-model="form.password"
          type="password"
          name="password"
          label="密码"
          placeholder="密码"
          clearable
        />
      </van-cell-group>
      <div style="margin: 16px 16px 0">
        <van-button round block type="primary" native-type="submit" :loading="loading">
          登录
        </van-button>
      </div>
    </van-form>
    <!-- <div class="m-login-hint">默认账号 admin / admin123</div> -->
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { authApi } from '../../api'
import { setAuth } from '../../utils/auth'

const router = useRouter()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function doLogin() {
  if (!form.username || !form.password) {
    return showToast('请输入账号和密码')
  }
  loading.value = true
  try {
    const res = await authApi.login(form)
    if (res.user.role === 'student') {
      return showToast('学生账号请从学生端登录')
    }
    setAuth(res.token, res.user)
    if (res.must_change_password) {
      showToast('请先修改初始密码')
      router.replace('/admin/change-password?first=1')
      return
    }
    showToast({ type: 'success', message: '登录成功' })
    router.replace('/m/home')
  } catch (e) {
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.m-login {
  min-height: 100vh;
  background: linear-gradient(160deg, #0f172a 0%, #1e3a8a 55%, #2563eb 100%);
  padding-top: 60px;
}
.m-login-header {
  text-align: center;
  color: #fff;
  margin-bottom: 40px;
}
.m-logo {
  width: 64px;
  height: 64px;
  line-height: 64px;
  margin: 0 auto 12px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.15);
  font-size: 30px;
  font-weight: 700;
}
.m-login-header h1 {
  margin: 0;
  font-size: 22px;
}
.m-login-header p {
  margin: 6px 0 0;
  font-size: 13px;
  opacity: 0.8;
}
.m-login-hint {
  margin-top: 24px;
  text-align: center;
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
}
</style>
