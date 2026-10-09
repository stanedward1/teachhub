<template>
  <div class="md-body" v-html="html"></div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  content: { type: String, default: '' },
})

const html = computed(() => {
  if (!props.content) return '<p style="color:#9ca3af">暂无内容</p>'
  const rendered = marked.parse(props.content || '', { breaks: true })
  // XSS 防护：对渲染后的 HTML 做白名单过滤（移除 script / 内联事件 / javascript: 协议等）
  return DOMPurify.sanitize(rendered)
})
</script>
