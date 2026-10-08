<template>
  <el-drawer
    :model-value="modelValue"
    direction="rtl"
    size="560px"
    :with-header="false"
    @update:model-value="(v) => emit('update:modelValue', v)"
  >
    <div class="cc-wrap">
      <div class="cc-header">
        <div class="cc-title">
          <el-icon><ChatLineSquare /></el-icon>
          <span>学伴会话（只读）</span>
        </div>
        <el-button link size="small" @click="emit('update:modelValue', false)">关闭</el-button>
      </div>

      <div class="cc-readonly-tip">
        <el-icon><View /></el-icon>
        <span>教师查看模式：仅展示学生提问原文与 AI 回答全文，不可编辑或删除。</span>
      </div>

      <div class="cc-body" v-loading="loading">
        <div v-if="meta" class="cc-meta">
          <span class="cc-student">{{ meta.student_name || '未知学生' }}</span>
          <el-tag v-if="meta.assignment_title" size="small" effect="plain">
            {{ meta.assignment_title }}
          </el-tag>
          <el-tag size="small" type="info">共 {{ meta.turns || 0 }} 轮</el-tag>
          <el-tag v-if="refusedCount > 0" size="small" type="warning">
            拒答 {{ refusedCount }} 次
          </el-tag>
        </div>

        <div v-if="error" class="cc-error">{{ error }}</div>

        <div v-else-if="!loading && !messages.length" class="cc-empty">该学生在本作业下暂无学伴对话</div>

        <div
          v-for="m in messages"
          :key="m.id"
          class="cc-row"
          :class="m.role === 'user' ? 'cc-row-user' : 'cc-row-ai'"
        >
          <el-avatar
            :size="28"
            class="cc-avatar"
            :class="m.role === 'user' ? 'cc-av-user' : 'cc-av-ai'"
          >
            {{ m.role === 'user' ? '生' : 'AI' }}
          </el-avatar>
          <div class="cc-bubble-col">
            <div v-if="m.role === 'assistant' && m.refused" class="cc-refused-tip">
              <el-icon><WarningFilled /></el-icon>
              <span>学伴已按规则拒答（未直接给出答案）</span>
            </div>
            <div
              class="cc-bubble"
              :class="{
                'cc-bubble-user': m.role === 'user',
                'cc-bubble-ai': m.role === 'assistant',
                'cc-bubble-refused': m.role === 'assistant' && m.refused,
              }"
            >
              <div v-if="m.role === 'user'" class="cc-text">{{ m.content }}</div>
              <Markdown v-else :content="m.content" />
            </div>
            <div v-if="m.created_at" class="cc-time">{{ m.created_at }}</div>
          </div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import Markdown from './Markdown.vue'
import { homeworkApi } from '../api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // 会话 id：null 时表示未选中，面板展示空态
  conversationId: { type: [Number, String], default: null },
})
const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const error = ref('')
const meta = ref(null)
const messages = ref([])
const refusedCount = ref(0)

// 组件卸载后到达的异步回调不再写状态（防止对已销毁组件赋值）
let unmounted = false

/**
 * 载入单个会话的完整消息（学生提问原文 + AI 全文，设计 §14.2）。
 * 教师侧严格只读：本组件不提供任何写入口（对应硬约束 X6）。
 */
async function load() {
  if (!props.conversationId) {
    meta.value = null
    messages.value = []
    refusedCount.value = 0
    error.value = ''
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await homeworkApi.companionConversationDetail(props.conversationId)
    if (unmounted) return
    meta.value = {
      student_name: res?.student_name || '',
      assignment_title: res?.assignment_title || '',
      turns: res?.turns || 0,
    }
    const list = Array.isArray(res?.messages) ? res.messages : []
    messages.value = list.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      refused: !!m.refused,
      created_at: m.created_at || '',
    }))
    refusedCount.value = messages.value.filter((m) => m.refused).length
  } catch (e) {
    if (unmounted) return
    messages.value = []
    // 越权一律 404（不泄露会话存在性，设计 §14.2 / X5）；其余失败由全局拦截器提示
    error.value =
      e?.response?.status === 404 ? '会话不存在或不在你的班级范围内' : '加载学伴会话失败'
  } finally {
    if (!unmounted) loading.value = false
  }
}

// 打开面板或切换会话 id 时重新载入
watch(
  () => [props.modelValue, props.conversationId],
  ([open]) => {
    if (open) load()
  }
)

onBeforeUnmount(() => {
  unmounted = true
})
</script>

<style scoped>
.cc-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.cc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #f3f4f6;
}
.cc-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: #5b21b6;
  font-size: 15px;
}
.cc-readonly-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  background: #f5f3ff;
  border-bottom: 1px solid #ddd6fe;
  color: #6d28d9;
  font-size: 12px;
}
.cc-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #f8fafc;
}
.cc-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.cc-student {
  font-weight: 600;
  color: #111827;
  font-size: 14px;
}
.cc-empty,
.cc-error {
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
  padding: 32px 0;
}
.cc-error {
  color: #b91c1c;
}
.cc-row {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
  align-items: flex-start;
}
.cc-row-user {
  flex-direction: row-reverse;
}
.cc-avatar {
  flex-shrink: 0;
  font-size: 12px;
}
.cc-av-user {
  background: #4f46e5;
}
.cc-av-ai {
  background: #0ea5e9;
}
.cc-bubble-col {
  max-width: 82%;
}
.cc-bubble {
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}
.cc-bubble-user {
  background: #4f46e5;
  color: #fff;
  border-top-right-radius: 2px;
}
.cc-bubble-ai {
  background: #fff;
  color: #111827;
  border: 1px solid #e5e7eb;
  border-top-left-radius: 2px;
}
.cc-bubble-refused {
  background: #f1f5f9;
  border-color: #cbd5e1;
  color: #475569;
}
.cc-bubble :deep(.md-body) {
  font-size: 13px;
  line-height: 1.6;
}
.cc-bubble :deep(.md-body) pre {
  margin: 6px 0;
  padding: 8px 10px;
  font-size: 12px;
  overflow-x: auto;
}
.cc-text {
  white-space: pre-wrap;
}
.cc-refused-tip {
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
.cc-time {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 3px;
}
.cc-row-user .cc-time {
  text-align: right;
}
</style>
