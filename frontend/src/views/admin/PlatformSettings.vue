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

      <!-- ============ AI 批改总开关 ============ -->
      <div class="section-label section-gap">AI 批改</div>
      <el-form label-width="140px" v-loading="aiLoading">
        <el-form-item label="AI 批改总开关">
          <el-switch
            v-model="aiForm.enabled"
            :loading="aiSaving"
            :disabled="aiLoading"
            active-text="开启"
            inactive-text="关闭"
            @change="saveAiGrading"
          />
          <div class="hint">
            平台级统一开关，对所有学校生效。关闭时学生提交作业不会产生任何 AI 调用。
          </div>
        </el-form-item>

        <el-form-item label="优秀作品自动入库">
          <el-switch
            v-model="aiForm.auto_publish_excellent"
            :loading="aiSaving"
            :disabled="aiLoading || !aiForm.enabled"
            active-text="自动入库"
            inactive-text="教师确认"
            @change="onToggleAutoPublish"
          />
          <div class="hint">
            默认关闭：AI 只推荐候选，需教师确认后才进入优秀作品。开启后 AI 推荐的优秀作品将
            <strong>自动发布到学生端</strong>。
          </div>
        </el-form-item>

        <el-form-item label="每日调用上限">
          <el-input-number v-model="aiForm.daily_limit" :min="1" :max="100000" :disabled="aiLoading" />
          <el-button type="primary" plain style="margin-left: 12px" :loading="aiSaving" @click="saveAiGrading">
            保存
          </el-button>
          <div class="hint">总开关为平台级，这里是唯一的成本刹车；超限当日自动停止批改。</div>
        </el-form-item>

        <el-form-item label="单次 max_tokens">
          <el-input-number
            v-model="aiForm.max_tokens"
            :min="64"
            :max="32000"
            :step="64"
            :disabled="aiLoading"
          />
        </el-form-item>

        <el-form-item label="当前状态">
          <el-tag v-if="!aiForm.configured" type="warning" size="small">凭证未配置</el-tag>
          <el-tag v-else-if="aiForm.enabled" type="success" size="small">运行中</el-tag>
          <el-tag v-else type="info" size="small">已关闭</el-tag>
          <span class="usage">今日已用 {{ aiForm.today_call_count }} / {{ aiForm.daily_limit }} 次</span>
        </el-form-item>
      </el-form>

      <!-- ============ AI 服务凭证 ============ -->
      <div class="section-label section-gap">AI 服务凭证</div>
      <el-form label-width="140px" v-loading="credLoading">
        <el-form-item label="服务商">
          <el-input v-model="credForm.provider" placeholder="deepseek" />
        </el-form-item>
        <el-form-item label="服务地址">
          <el-input v-model="credForm.base_url" placeholder="https://api.deepseek.com" />
          <div class="hint">填到域名或 /v1 即可，系统会自动补全 /v1/chat/completions。</div>
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input v-model="credForm.model" placeholder="deepseek-chat" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="credForm.api_key"
            type="password"
            show-password
            autocomplete="new-password"
            :placeholder="credMasked ? `已配置（${credMasked}），留空表示不修改` : '请输入 API Key'"
          />
          <div class="hint">密钥加密存储，任何接口都不回显明文。</div>
        </el-form-item>
        <el-form-item label="图片附件">
          <el-switch
            v-model="credForm.vision_enabled"
            active-text="参与批改"
            inactive-text="不参与"
            @change="onVisionChange"
          />
          <div class="hint">
            deepseek-flash 原生支持图片输入（仅 JPEG/PNG/GIF/WebP），建议开启；关闭后图片会被静默跳过。
            所配模型支持多模态时才开启；关闭时图片附件会标注「未参与批改」。
          </div>
        </el-form-item>
        <el-form-item label="启用凭证">
          <el-switch v-model="credForm.enabled" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="credSaving" @click="saveCredential">保存凭证</el-button>
          <el-button :loading="testing" @click="testCredential">测试连接</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi } from '../../api'

// ---------------- 注册管控（平台级「学生自助注册」总开关） ----------------
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

// ---------------- AI 批改开关（平台级，无按校粒度） ----------------
const aiLoading = ref(false)
const aiSaving = ref(false)
const aiForm = reactive({
  enabled: false,
  auto_publish_excellent: false,
  daily_limit: 200,
  max_tokens: 1200,
  configured: false,
  today_call_count: 0,
})

async function loadAi() {
  aiLoading.value = true
  try {
    Object.assign(aiForm, await adminApi.aiGrading())
  } catch (e) {
    console.error('[PlatformSettings] 加载 AI 批改开关失败:', e)
  } finally {
    aiLoading.value = false
  }
}

async function saveAiGrading() {
  aiSaving.value = true
  try {
    const res = await adminApi.setAiGrading({
      enabled: aiForm.enabled,
      auto_publish_excellent: aiForm.auto_publish_excellent,
      daily_limit: aiForm.daily_limit,
      max_tokens: aiForm.max_tokens,
    })
    Object.assign(aiForm, res)
    ElMessage.success('已保存')
  } catch (e) {
    // 保存失败：以服务端真值覆盖本地，避免界面与后端不一致
    await loadAi()
    ElMessage.error('设置失败，请稍后重试')
    console.error('[PlatformSettings] 保存 AI 批改开关失败:', e)
  } finally {
    aiSaving.value = false
  }
}

async function onToggleAutoPublish(val) {
  if (val) {
    try {
      await ElMessageBox.confirm(
        '开启后，AI 推荐的优秀作品将【自动发布到学生端】，无需教师逐条确认。确定开启吗？',
        '重要提示',
        { type: 'warning', confirmButtonText: '确认开启', cancelButtonText: '取消' }
      )
    } catch {
      // 用户取消：回滚开关（el-switch 的 v-model 已先行变更）
      aiForm.auto_publish_excellent = false
      return
    }
  }
  await saveAiGrading()
}

// ---------------- AI 服务凭证（只写不回显） ----------------
const credLoading = ref(false)
const credSaving = ref(false)
const testing = ref(false)
const credMasked = ref('')
const credForm = reactive({
  provider: 'deepseek',
  base_url: '',
  model: '',
  api_key: '',
  vision_enabled: false,
  enabled: true,
})

// 管理员是否手动动过「图片附件」开关；手动改过后绝不被服务商/模型的自动推断覆盖
const visionTouched = ref(false)
// 加载已存凭证期间抑制自动推断，避免覆盖服务端显式存储的值
const suppressInfer = ref(false)

// 与后端 backend/app/services/ai_admin_service.py::default_vision_enabled 口径一致：
// base_url 含 "deepseek" 且 model 含 "flash"/"vision" → 默认开启视觉。
function inferVisionEnabled(baseUrl, model) {
  if (!baseUrl || !model) return false
  const bu = baseUrl.toLowerCase()
  const m = model.toLowerCase()
  return bu.includes('deepseek') && (m.includes('flash') || m.includes('vision'))
}

function onVisionChange() {
  visionTouched.value = true
}

// 管理员没手动改过开关时，按服务商与模型自动推断 vision_enabled，行为可见而非静默
watch(
  () => [credForm.base_url, credForm.model],
  () => {
    if (!visionTouched.value && !suppressInfer.value) {
      credForm.vision_enabled = inferVisionEnabled(credForm.base_url, credForm.model)
    }
  }
)

async function loadCredential() {
  credLoading.value = true
  suppressInfer.value = true
  try {
    const res = await adminApi.aiCredential()
    credMasked.value = res.api_key_masked || ''
    credForm.provider = res.provider || 'deepseek'
    credForm.base_url = res.base_url || ''
    credForm.model = res.model || ''
    credForm.vision_enabled = !!res.vision_enabled
    credForm.enabled = res.configured ? !!res.enabled : true
    // 密钥永不回填：留空即「不修改」
    credForm.api_key = ''
  } catch (e) {
    console.error('[PlatformSettings] 加载 AI 凭证失败:', e)
  } finally {
    credLoading.value = false
    // 等上面的赋值触发的 watch 落定后再放开推断，避免覆盖服务端显式值
    nextTick(() => {
      suppressInfer.value = false
    })
  }
}

async function saveCredential() {
  if (!credForm.base_url.trim() || !credForm.model.trim()) {
    return ElMessage.warning('请填写服务地址与模型名称')
  }
  credSaving.value = true
  try {
    const res = await adminApi.setAiCredential({
      provider: credForm.provider.trim() || 'deepseek',
      base_url: credForm.base_url.trim(),
      model: credForm.model.trim(),
      api_key: credForm.api_key.trim() || null,
      vision_enabled: credForm.vision_enabled,
      enabled: credForm.enabled,
    })
    credMasked.value = res.api_key_masked || ''
    credForm.api_key = ''
    ElMessage.success('凭证已保存')
    await Promise.all([loadCredential(), loadAi()])
  } catch (e) {
    ElMessage.error('保存失败，请稍后重试')
    console.error('[PlatformSettings] 保存 AI 凭证失败:', e)
  } finally {
    credSaving.value = false
  }
}

async function testCredential() {
  testing.value = true
  try {
    // 表单填了地址与模型就用未保存的配置试连；否则回退到已存凭证
    const body =
      credForm.base_url.trim() && credForm.model.trim()
        ? {
            provider: credForm.provider.trim() || 'deepseek',
            base_url: credForm.base_url.trim(),
            model: credForm.model.trim(),
            api_key: credForm.api_key.trim() || null,
            vision_enabled: credForm.vision_enabled,
            enabled: credForm.enabled,
          }
        : null
    const res = await adminApi.testAiCredential(body)
    if (res.ok) {
      ElMessage.success(`连接成功（${res.elapsed_ms} ms）`)
    } else {
      ElMessage.error(`连接失败：${res.message}`)
    }
  } catch (e) {
    console.error('[PlatformSettings] 测试 AI 凭证失败:', e)
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  load()
  loadAi()
  loadCredential()
})
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

.section-gap {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid #f3f4f6;
}

.hint {
  font-size: 12px;
  color: #9ca3af;
  line-height: 1.6;
  margin-top: 6px;
}

.usage {
  margin-left: 12px;
  font-size: 12px;
  color: #6b7280;
}
</style>
