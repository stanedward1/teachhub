<template>
  <div class="m-pwd">
    <div class="m-pwd-header">
      <h1>修改密码</h1>
      <p>首次登录或密码重置后需修改密码</p>
    </div>
    <van-form @submit="save">
      <van-cell-group inset>
        <van-field
          v-model="old_password"
          type="password"
          name="old_password"
          label="原密码"
          placeholder="请输入原密码"
          clearable
        />
        <van-field
          v-model="new_password"
          type="password"
          name="new_password"
          label="新密码"
          placeholder="至少 8 位，含字母和数字"
          clearable
        />
      </van-cell-group>
      <div style="margin: 16px">
        <van-button round block type="primary" native-type="submit" :loading="loading">
          确认修改
        </van-button>
      </div>
    </van-form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { authApi } from '../../api'
import { getToken, getUser, setAuth } from '../../utils/auth'

const router = useRouter()
const old_password = ref('')
const new_password = ref('')
const loading = ref(false)

async function save() {
  if (!old_password.value || !new_password.value) {
    return showToast('请填写原密码和新密码')
  }
  loading.value = true
  try {
    await authApi.changePassword({
      old_password: old_password.value,
      new_password: new_password.value
    })
    // 改密后清除强制改密标记
    setAuth(getToken(), { ...getUser(), must_change_password: false })
    showToast({ type: 'success', message: '密码修改成功' })
    router.replace('/m/home')
  } catch (e) {
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.m-pwd {
  min-height: 100vh;
  background: var(--bg-tertiary, #f7f8fa);
  padding-top: 40px;
}
.m-pwd-header {
  text-align: center;
  margin-bottom: 24px;
}
.m-pwd-header h1 {
  margin: 0;
  font-size: 20px;
}
.m-pwd-header p {
  margin: 8px 0 0;
  font-size: 13px;
  color: #969799;
}
</style>
