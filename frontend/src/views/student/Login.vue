<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="brand">
        <div class="brand-mark">S</div>
        <div>
          <h1>StudyHub</h1>
          <p>上机作业提交平台</p>
        </div>
      </div>

      <el-select
        v-model="schoolId"
        placeholder="选择学校"
        size="large"
        filterable
        style="width: 100%; margin-bottom: 18px"
        @change="onSchoolChange"
      >
        <el-option v-for="s in schools" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>

      <el-tabs v-model="tab" class="tabs">
        <el-tab-pane label="学生登录" name="login">
          <el-form @submit.prevent="doLogin">
            <el-form-item>
              <el-select
                v-model="form.class_id"
                placeholder="选择班级"
                size="large"
                style="width: 100%"
              >
                <el-option
                  v-for="c in classes"
                  :key="c.id"
                  :label="classLabel(c)"
                  :value="c.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-input v-model="form.username" placeholder="姓名" size="large" />
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="form.password"
                type="password"
                placeholder="密码"
                size="large"
                show-password
                @keyup.enter="doLogin"
              />
            </el-form-item>
            <el-button
              type="primary"
              size="large"
              style="width: 100%"
              :loading="loading"
              @click="doLogin"
            >
              登 录
            </el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane v-if="registerEnabled" label="学生注册" name="register">
          <el-form @submit.prevent="doRegister">
            <el-form-item>
              <el-select
                v-model="reg.class_id"
                placeholder="选择班级"
                size="large"
                style="width: 100%"
              >
                <el-option
                  v-for="c in classes"
                  :key="c.id"
                  :label="classLabel(c)"
                  :value="c.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-input v-model="reg.name" placeholder="姓名" size="large" />
            </el-form-item>
            <el-form-item>
              <el-input
                v-model="reg.password"
                type="password"
                placeholder="密码（至少 6 位）"
                size="large"
                show-password
                @keyup.enter="doRegister"
              />
            </el-form-item>
            <el-button
              type="primary"
              size="large"
              style="width: 100%"
              :loading="loading"
              @click="doRegister"
            >
              注 册
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <div class="hint">教师请前往 <router-link to="/admin/login">管理后台登录</router-link></div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi, metaApi } from '../../api'
import { clearRefreshToken, getLastSchoolId, setAuth, setLastSchoolId } from '../../utils/auth'

const router = useRouter()
const tab = ref('login')
const loading = ref(false)
// 平台超管可关闭学生自助注册；接口失败时按关闭处理（安全降级）
const registerEnabled = ref(false)
const classes = ref([])
const schools = ref([])
const schoolId = ref(getLastSchoolId())

const form = reactive({ class_id: null, username: '', password: '' })
const reg = reactive({ class_id: null, name: '', password: '' })

// 班级代码与名称不一致时一并展示（如名称「2026级计算机2班」/ 代码「2622」），
// 避免只看到名称而误判「下拉框里没有这个班」
const classLabel = (c) => (c.code && c.code !== c.name ? `${c.name}（${c.code}）` : c.name)

async function loadClasses() {
  try {
    const res = await metaApi.classes(schoolId.value)
    classes.value = res.items
  } catch (e) {
    console.error('[StudentLogin] 加载班级列表失败:', e)
  }
}

function onSchoolChange() {
  setLastSchoolId(schoolId.value)
  form.class_id = null
  reg.class_id = null
  loadClasses()
}

onMounted(async () => {
  try {
    const res = await authApi.registrationStatus()
    registerEnabled.value = res.allow_registration === true
  } catch (e) {
    console.error('[StudentLogin] 获取注册开关状态失败:', e)
    registerEnabled.value = false
  }
  try {
    const res = await authApi.publicSchools()
    schools.value = res.items || []
  } catch (e) {
    console.error('[StudentLogin] 加载学校列表失败:', e)
  }
  await loadClasses()
})

watch(schoolId, () => setLastSchoolId(schoolId.value))

// 注册入口被关闭时，若当前停留在注册页签则回落到登录页签
watch(registerEnabled, (enabled) => {
  if (!enabled && tab.value === 'register') tab.value = 'login'
})

async function doLogin() {
  if (!schoolId.value || !form.class_id || !form.username || !form.password) {
    return ElMessage.warning('请选择学校、班级并填写姓名和密码')
  }
  loading.value = true
  try {
    const res = await authApi.login({
      class_id: form.class_id,
      username: form.username,
      password: form.password,
      school_id: schoolId.value,
    })
    setAuth(res.token, res.user, res.refresh_token)
    if (res.must_change_password) {
      ElMessage.warning('首次登录或密码已重置，请先修改密码')
      router.push('/profile')
      return
    }
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e) {
  } finally {
    loading.value = false
  }
}

async function doRegister() {
  if (!registerEnabled.value) {
    return ElMessage.warning('当前未开放注册，请联系管理员')
  }
  if (!schoolId.value || !reg.class_id || !reg.name) {
    return ElMessage.warning('请选择学校、班级并填写姓名')
  }
  // 密码改为必填并做基本校验：后端 RegisterRequest.password 已由「默认 123456」改为必填
  // （min_length=6）。前端不再用 `|| '123456'` 兜底弱口令（§2.5）。
  if (!reg.password) {
    return ElMessage.warning('请设置登录密码')
  }
  if (reg.password.length < 6) {
    return ElMessage.warning('密码至少 6 位')
  }
  loading.value = true
  try {
    const res = await authApi.register({
      name: reg.name,
      class_id: reg.class_id,
      password: reg.password,
      school_id: schoolId.value,
    })
    // 注册即自动登录，是**另一个账号**的新会话。
    // 后端目前仅在 login 回传 refresh_token，register 不回传 —— 若沿用上一个账号遗留的
    // refresh_token，access token 过期后会拿旧账号身份去刷新（§3.6）。故：有新 token 就写入，
    // 没有就显式清除旧值（宁可本次会话无静默刷新，也不能身份串号）。
    if (res.refresh_token) {
      setAuth(res.token, res.user, res.refresh_token)
    } else {
      setAuth(res.token, res.user)
      clearRefreshToken()
    }
    // 弱口令注册（后端置 must_change_password）需与登录一致地提示并跳转改密，
    // 否则等于「接受弱口令却不告知」（§2.5）
    if (res.must_change_password) {
      ElMessage.warning('注册成功，请先设置新密码')
      router.push('/profile')
      return
    }
    ElMessage.success('注册成功')
    router.push('/')
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
  background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 50%, #4f46e5 100%);
  padding: 20px;
}
.login-card {
  width: 400px;
  background: #fff;
  border-radius: 16px;
  padding: 32px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
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
.tabs {
  margin-top: 8px;
}
.hint {
  text-align: center;
  margin-top: 16px;
  font-size: 13px;
  color: #6b7280;
}
.hint a {
  color: #2563eb;
}
</style>
