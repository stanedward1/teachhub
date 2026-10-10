<template>
  <el-drawer
    :model-value="modelValue"
    direction="rtl"
    size="420px"
    :with-header="false"
    :close-on-click-modal="true"
    @update:model-value="(v) => emit('update:modelValue', v)"
    @close="onClosed"
  >
    <div class="cp-wrap">
      <!-- 顶部标题 + 清空 -->
      <div class="cp-header">
        <div class="cp-title">
          <el-icon><MagicStick /></el-icon>
          <span>AI 学伴</span>
        </div>
        <el-button
          link
          type="primary"
          size="small"
          :disabled="!messages.length || sending || clearing"
          @click="clear"
        >
          清空对话
        </el-button>
      </div>

      <!-- 免责声明（固定顶部，设计 §6.3 / F12） -->
      <div class="cp-disclaimer">
        <el-icon><InfoFilled /></el-icon>
        <span>AI 生成，仅供参考，鼓励自己思考</span>
      </div>

      <!-- 今日剩余次数（每生独立配额，docs/DESIGN-AI学伴配额.md D4）：
           remaining 为 null 时不展示，避免闪出错误值；仅显示剩余（不暴露上限/平台口径）。 -->
      <div v-if="remaining !== null" class="cp-quota">
        <el-icon><Timer /></el-icon>
        <span
          >今日剩余 <b>{{ remaining }}</b> 次</span
        >
      </div>

      <!-- 消息区 -->
      <div ref="scrollRef" class="cp-body" v-loading="loadingHistory">
        <div v-if="!messages.length && !loadingHistory" class="cp-empty">
          <p>有问题尽管问我，我会引导你自己找到答案。</p>
          <div class="cp-chips">
            <el-tag
              v-for="q in quickQuestions"
              :key="q"
              class="cp-chip"
              effect="plain"
              @click="askQuick(q)"
            >
              {{ q }}
            </el-tag>
          </div>
        </div>

        <div
          v-for="(m, i) in messages"
          :key="m._key"
          class="cp-row"
          :class="m.role === 'user' ? 'cp-row-user' : 'cp-row-ai'"
        >
          <el-avatar
            :size="28"
            class="cp-avatar"
            :class="m.role === 'user' ? 'cp-av-user' : 'cp-av-ai'"
          >
            {{ m.role === 'user' ? '我' : 'AI' }}
          </el-avatar>
          <div class="cp-bubble-col">
            <!-- 拒答的 assistant 消息：区别化呈现（浅色提示条） -->
            <div v-if="m.role === 'assistant' && m.refused" class="cp-refused-tip">
              <el-icon><WarningFilled /></el-icon>
              <span>这不是「不会答」，而是规则不允许直接给答案 —— 请先自己想一想。</span>
            </div>
            <div
              class="cp-bubble"
              :class="{
                'cp-bubble-user': m.role === 'user',
                'cp-bubble-ai': m.role === 'assistant',
                'cp-bubble-refused': m.role === 'assistant' && m.refused,
                'cp-bubble-error': m.role === 'assistant' && m.failed,
              }"
            >
              <!-- 学生提问原文按纯文本展示（避免其输入被当成 Markdown 指令渲染） -->
              <div v-if="m.role === 'user'" class="cp-text">{{ m.content }}</div>
              <!-- AI 回答走 Markdown 渲染，代码片段可读 -->
              <Markdown v-else-if="!m.failed" :content="m.content" />
              <template v-else>
                <div class="cp-err-row">
                  <span>{{ m.content }}</span>
                  <el-button link type="primary" size="small" @click="retry(i)">重试</el-button>
                </div>
              </template>
            </div>
            <div v-if="m.role === 'assistant' && m.truncated" class="cp-truncated">
              回答较长，已截断
            </div>
            <div v-if="m.createdAt" class="cp-time">{{ m.createdAt }}</div>
          </div>
        </div>

        <!-- 加载态：可撑住 25s 的等待（设计 §2.2） -->
        <div v-if="sending" class="cp-row cp-row-ai">
          <el-avatar :size="28" class="cp-avatar cp-av-ai">AI</el-avatar>
          <div class="cp-bubble cp-bubble-ai cp-thinking">
            <el-icon class="cp-spin"><Loading /></el-icon>
            <span>AI 正在思考…（已等待 {{ waitedSeconds }} 秒）</span>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="cp-footer">
        <el-input
          v-model="draft"
          type="textarea"
          :rows="2"
          resize="none"
          maxlength="1500"
          show-word-limit
          placeholder="输入你的问题，例如：这题该从哪里入手？"
          :disabled="sending"
          @keydown.enter.exact.prevent="send()"
        />
        <div class="cp-actions">
          <span class="cp-hint">Enter 发送 / Shift+Enter 换行</span>
          <el-button
            type="primary"
            size="small"
            :loading="sending"
            :disabled="sending || !draft.trim()"
            @click="send()"
          >
            发送
          </el-button>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import Markdown from './Markdown.vue'
import { homeworkApi } from '../api'

const props = defineProps({
  // 打开状态由父组件控制（v-model）
  modelValue: { type: Boolean, default: false },
  // 当前作业 id：用于拉取历史 / 提问 / 清空
  assignmentId: { type: [Number, String], default: null },
})
const emit = defineEmits(['update:modelValue'])

// 快捷提问 chip（设计 §6.3 / F11）
const quickQuestions = ['这题考什么知识点', '我该从哪里开始', '帮我检查思路']

const messages = ref([])
const draft = ref('')
const sending = ref(false)
const clearing = ref(false)
const loadingHistory = ref(false)
// 每生独立配额：今日剩余次数（null = 尚未拉到 / 拉取失败，此时不展示以免闪错值）
const remaining = ref(null)
// 失败重试复用原提问（设计 §6.3：不复用学生输入即视为不合格）
const failedQuestion = ref('')
const waitedSeconds = ref(0)
const scrollRef = ref(null)

// 计时器：必须四处清理（启动前清旧、@close、onBeforeUnmount）
let timer = null
// 组件是否已卸载：卸载后到达的异步回调不再写状态
let unmounted = false

/** 唯一 key，避免已有历史 id 与本地乐观消息冲突 */
let localSeq = 0
function nextKey() {
  localSeq += 1
  return `local-${localSeq}`
}

/**
 * 消息对象工厂：4 处同构字面量收敛（历史映射 / 乐观气泡 / 成功回答 / 失败气泡）。
 * 默认自增 _key；overrides 显式传入 _key（服务端历史 id）时不消耗本地序号，
 * 保持既有 _key 生成顺序与数值行为不变。
 * @param {object} [overrides] 覆盖默认值的字段（如 role/content/failed/question/_key）
 */
function makeMsg(overrides = {}) {
  return {
    _key: overrides._key ?? nextKey(),
    role: 'user',
    content: '',
    refused: false,
    truncated: false,
    failed: false,
    createdAt: '',
    ...overrides,
  }
}

function startTimer() {
  clearTimer()
  waitedSeconds.value = 0
  timer = setInterval(() => {
    waitedSeconds.value += 1
  }, 1000)
}

function clearTimer() {
  if (timer !== null) {
    clearInterval(timer)
    timer = null
  }
}

async function scrollToBottom() {
  await nextTick()
  const el = scrollRef.value
  if (el) el.scrollTop = el.scrollHeight
}

/** 打开抽屉时载入服务端历史（切作业由父组件 :key 强制重建，这里只兜底） */
async function loadHistory() {
  if (!props.assignmentId) return
  loadingHistory.value = true
  try {
    const res = await homeworkApi.companionHistory(props.assignmentId)
    if (unmounted) return
    const list = Array.isArray(res?.messages) ? res.messages : []
    messages.value = list.map((m) =>
      makeMsg({
        _key: `srv-${m.id}`,
        role: m.role,
        content: m.content,
        refused: !!m.refused,
        createdAt: m.created_at || '',
      })
    )
    await scrollToBottom()
  } catch (e) {
    // 首屏无会话不应报错：后端契约返 conversation_id=null + 空数组；
    // 真正失败的原因由全局拦截器提示，这里静默降级为空列表
    if (unmounted) return
    messages.value = []
  } finally {
    if (!unmounted) loadingHistory.value = false
  }
}

/** 学生点击快捷提问：直接以该问题发送 */
function askQuick(q) {
  draft.value = q
  send()
}

/**
 * 拉取本生今日剩余次数（每生独立配额，docs/DESIGN-AI学伴配额.md D4）。
 * 打开抽屉 / 提问成功 / 提问失败后各调一次；**不本地减一** —— 服务端 DB 是唯一权威源。
 * 失败静默降级（remaining 保持原值或 null），不阻塞主流程。
 */
async function loadQuota() {
  if (!props.assignmentId) return
  try {
    const res = await homeworkApi.companionQuota(props.assignmentId)
    if (unmounted) return
    remaining.value = typeof res?.remaining === 'number' ? res.remaining : null
  } catch (e) {
    // 额度查询失败不打扰学生：保留上一次读数（或 null 不展示）
  }
}

/**
 * 发送提问。
 * 防重入守卫不得跨 await：sending 在任何 await 之前置位，try/finally 复位。
 * @param {string} [questionOverride] 重试时沿用原提问
 */
async function send(questionOverride) {
  if (sending.value) return
  const question = (questionOverride ?? draft.value).trim()
  if (!question) return

  // 配额守卫：已知剩余为 0 时直接提示，不再发起请求（避免反复撞 429）。
  if (remaining.value !== null && remaining.value <= 0) {
    ElMessage.warning('今日 AI 学伴次数已用完，明天再来吧')
    return
  }

  // 乐观展示学生气泡
  messages.value.push(makeMsg({ content: question }))
  failedQuestion.value = question
  draft.value = ''
  await scrollToBottom()

  sending.value = true
  startTimer()
  try {
    const res = await homeworkApi.companionAsk(props.assignmentId, { question })
    if (unmounted) return
    messages.value.push(
      makeMsg({
        role: 'assistant',
        content: res?.answer || '',
        refused: !!res?.refused,
        truncated: !!res?.truncated,
      })
    )
  } catch (e) {
    if (unmounted) return
    // 失败气泡 + 重试按钮；可读原因优先取后端 detail（403/429/502/503 都给可读文案）
    const detail = e?.response?.data?.detail
    const reason =
      typeof detail === 'string' && detail.trim()
        ? detail
        : e?.code === 'ECONNABORTED'
          ? '请求超时，请重试'
          : 'AI 暂时无法回答，请稍后重试'
    messages.value.push(
      makeMsg({
        role: 'assistant',
        content: reason,
        failed: true,
        // 失败气泡携带原提问：多个失败气泡并存时，retry 按各自气泡重试正确的提问
        question,
      })
    )
  } finally {
    clearTimer()
    if (!unmounted) {
      sending.value = false
      // 无论成功失败都重拉权威剩余次数（429 时把 remaining 拉正为 0，使 UI 与真相一致）
      await loadQuota()
      await scrollToBottom()
    }
  }
}

/** 失败重试：复用原提问（会重新消耗 1 次额度） */
function retry(index) {
  // 重试前先看剩余次数：已用尽则不重试（修复「反复撞 429」的缺陷，D4）
  if (remaining.value !== null && remaining.value <= 0) {
    ElMessage.warning('今日 AI 学伴次数已用完，明天再来吧')
    return
  }
  // 优先取该失败气泡自带的提问（多个失败气泡并存时不串位），
  // 兜底走 failedQuestion（兼容旧消息对象 / 历史路径）
  const question = messages.value[index]?.question ?? failedQuestion.value
  if (!question) return
  // 提问气泡 + 失败回答气泡一起移除，交由 send 重建，避免提问重复
  // （仅删失败回答会让 send 再 push 一条新的用户气泡，原提问留在列表里）
  const hasPrevUser = index > 0 && messages.value[index - 1]?.role === 'user'
  messages.value.splice(hasPrevUser ? index - 1 : index, hasPrevUser ? 2 : 1)
  send(question)
}

/** 清空对话：二次确认 → 调接口 → 清空本地 */
async function clear() {
  if (clearing.value) return
  try {
    await ElMessageBox.confirm('确定清空本作业的学伴对话吗？清空后无法恢复。', '清空对话', {
      type: 'warning',
      confirmButtonText: '清空',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  clearing.value = true
  try {
    await homeworkApi.clearCompanion(props.assignmentId)
    if (unmounted) return
    messages.value = []
    failedQuestion.value = ''
    ElMessage.success('已清空对话')
  } catch (e) {
    // 失败原因由全局拦截器提示
  } finally {
    if (!unmounted) clearing.value = false
  }
}

/** 抽屉关闭：清定时器（切作业/关闭时都走这里） */
function onClosed() {
  clearTimer()
}

onBeforeUnmount(() => {
  // 兜底：抽屉仍开着时组件卸载走不到 @close，只靠 @close 会泄漏定时器
  unmounted = true
  clearTimer()
})

// 首次挂载即拉取历史与今日剩余次数（父组件用 :key 保证切作业时重建）
loadHistory()
loadQuota()

defineExpose({ loadHistory, loadQuota })
</script>

<style scoped>
.cp-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 100%;
}
.cp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #f3f4f6;
}
.cp-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: #4f46e5;
  font-size: 15px;
}
.cp-disclaimer {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  background: #fffbeb;
  border-bottom: 1px solid #fde68a;
  color: #92400e;
  font-size: 12px;
}
.cp-quota {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  background: #eef2ff;
  border-bottom: 1px solid #e0e7ff;
  color: #4f46e5;
  font-size: 12px;
}
.cp-quota b {
  font-size: 13px;
}
.cp-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #f8fafc;
}
.cp-empty {
  text-align: center;
  color: #6b7280;
  font-size: 13px;
  padding: 24px 0;
}
.cp-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 14px;
}
.cp-chip {
  cursor: pointer;
}
.cp-row {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
  align-items: flex-start;
}
.cp-row-user {
  flex-direction: row-reverse;
}
.cp-avatar {
  flex-shrink: 0;
  font-size: 12px;
}
.cp-av-user {
  background: #4f46e5;
}
.cp-av-ai {
  background: #0ea5e9;
}
.cp-bubble-col {
  max-width: 82%;
}
.cp-bubble {
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}
.cp-bubble-user {
  background: #4f46e5;
  color: #fff;
  border-top-right-radius: 2px;
}
.cp-bubble-ai {
  background: #fff;
  color: #111827;
  border: 1px solid #e5e7eb;
  border-top-left-radius: 2px;
}
.cp-bubble-refused {
  background: #f1f5f9;
  border-color: #cbd5e1;
  color: #475569;
}
.cp-bubble-error {
  background: #fef2f2;
  border-color: #fecaca;
  color: #b91c1c;
}
.cp-bubble :deep(.md-body) {
  font-size: 13px;
  line-height: 1.6;
}
.cp-bubble :deep(.md-body) pre {
  margin: 6px 0;
  padding: 8px 10px;
  font-size: 12px;
  overflow-x: auto;
}
.cp-text {
  white-space: pre-wrap;
}
.cp-refused-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #64748b;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 5px 10px;
  margin-bottom: 4px;
}
.cp-truncated,
.cp-time {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 3px;
}
.cp-row-user .cp-truncated,
.cp-row-user .cp-time {
  text-align: right;
}
.cp-thinking {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
}
.cp-spin {
  animation: cp-rotate 1s linear infinite;
}
@keyframes cp-rotate {
  to {
    transform: rotate(360deg);
  }
}
.cp-err-row {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: space-between;
}
.cp-footer {
  padding: 12px 16px;
  border-top: 1px solid #f3f4f6;
  background: #fff;
}
.cp-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}
.cp-hint {
  font-size: 11px;
  color: #9ca3af;
}
</style>
