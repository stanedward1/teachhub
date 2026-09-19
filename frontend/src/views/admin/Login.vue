<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="brand">
        <div class="brand-mark">T</div>
        <div>
          <h1>TeachHub</h1>
          <p>教师 / 管理员后台</p>
        </div>
      </div>
      <el-form @submit.prevent="doLogin">
        <el-form-item>
          <el-select
            v-model="schoolId"
            placeholder="选择学校（平台超管可留空）"
            size="large"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="s in schools" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large">
            <template #prefix
              ><el-icon><User /></el-icon
            ></template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            @keyup.enter="doLogin"
          >
            <template #prefix
              ><el-icon><Lock /></el-icon
            ></template>
          </el-input>
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          style="width: 100%"
          :loading="loading"
          @click="doLogin"
        >
          进入后台
        </el-button>
      </el-form>
      <div class="hint">
        <!-- <div>默认账号：admin / admin123</div>
        <div>教师账号：teacher / 123456</div> -->
        <router-link to="/">返回学生端</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '../../api'
import { getLastSchoolId, setAuth, setLastSchoolId } from '../../utils/auth'

const router = useRouter()
const loading = ref(false)
const schools = ref([])
const schoolId = ref(getLastSchoolId())
const form = reactive({ username: '', password: '' })

onMounted(async () => {
  try {
    const res = await authApi.publicSchools()
    schools.value = res.items || []
  } catch (e) {
    console.error('[Login] 加载学校列表失败:', e)
  }
})

watch(schoolId, (v) => setLastSchoolId(v))

async function doLogin() {
  if (!form.username || !form.password) return ElMessage.warning('请输入用户名和密码')
  loading.value = true
  try {
    const res = await authApi.login({
      ...form,
      school_id: schoolId.value || undefined,
    })
    if (res.user.role === 'student') {
      return ElMessage.error('学生账号请从学生端登录')
    }
    setAuth(res.token, res.user, res.refresh_token)
    if (res.must_change_password) {
      ElMessage.warning('首次登录或密码已重置，请修改密码后再使用')
      router.push('/admin/change-password?first=1')
      return
    }
    ElMessage.success('登录成功')
    router.push('/admin')
  } catch (e) {
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #2563eb 100%);
  padding: 20px;
}
.login-card {
  width: 400px;
  background: #fff;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}
.brand-mark {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 700;
}
.brand h1 {
  margin: 0;
  font-size: 20px;
  color: #111827;
}
.brand p {
  margin: 2px 0 0;
  font-size: 13px;
  color: #6b7280;
}
.hint {
  margin-top: 20px;
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
  line-height: 1.8;
}
.hint a {
  color: #2563eb;
}
</style>
