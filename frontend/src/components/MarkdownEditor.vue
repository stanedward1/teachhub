<template>
  <div class="md-editor">
    <div class="md-toolbar">
      <el-button-group>
        <el-button size="small" title="标题" @click="wrap('## ', '')">H</el-button>
        <el-button size="small" title="加粗" @click="wrap('**', '**')"><b>B</b></el-button>
        <el-button size="small" title="斜体" @click="wrap('*', '*')"><i>I</i></el-button>
        <el-button size="small" title="代码" @click="wrap('`', '`')">`</el-button>
        <el-button size="small" title="代码块" @click="wrap('```\n', '\n```')">```</el-button>
        <el-button size="small" title="列表" @click="prefix('- ')">•</el-button>
        <el-button size="small" title="引用" @click="prefix('> ')">❝</el-button>
        <el-button size="small" title="链接" @click="wrap('[', '](https://)')">🔗</el-button>
        <el-button size="small" title="图片" @click="wrap('![', '](https://)')">🖼</el-button>
      </el-button-group>
      <el-upload :show-file-list="false" :http-request="doUpload" accept="image/*">
        <el-button size="small" type="primary" plain>上传图片</el-button>
      </el-upload>
    </div>
    <div class="md-panes">
      <el-input
        ref="taRef"
        type="textarea"
        :model-value="modelValue"
        :rows="rows"
        placeholder="支持 Markdown 语法…"
        @update:model-value="onInput"
      />
      <div class="md-preview">
        <Markdown :content="modelValue" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import Markdown from './Markdown.vue'
import { uploadFile } from '../api'

const props = defineProps({
  modelValue: { type: String, default: '' },
  rows: { type: Number, default: 18 },
  height: { type: String, default: '560px' }
})
const emit = defineEmits(['update:modelValue'])

function onInput(val) {
  emit('update:modelValue', val)
}

// 组件内的 textarea 引用：ElInput 通过 defineExpose 暴露 `textarea`（type=textarea 时的 DOM 节点）。
// 必须用组件内 ref 而非 `document.querySelector('.md-editor textarea')`——后者取的是**全文档第一个**
// 匹配项，同一弹窗内放两个 MarkdownEditor（如 Communications.vue 的 content / feedback）时，
// 点第二个编辑器的工具栏按钮会把文字插进第一个（§3.5）。
const taRef = ref(null)

function getTextarea() {
  return taRef.value?.textarea || null
}

function insert(text) {
  const ta = getTextarea()
  if (!ta) return
  const start = ta.selectionStart
  const end = ta.selectionEnd
  const value = props.modelValue
  const next = value.slice(0, start) + text + value.slice(end)
  emit('update:modelValue', next)
  setTimeout(() => {
    ta.focus()
    ta.selectionStart = ta.selectionEnd = start + text.length
  }, 0)
}

function wrap(before, after) {
  const ta = getTextarea()
  if (!ta) return
  const start = ta.selectionStart
  const end = ta.selectionEnd
  const value = props.modelValue
  const selected = value.slice(start, end) || '文本'
  const next = value.slice(0, start) + before + selected + after + value.slice(end)
  emit('update:modelValue', next)
}

function prefix(mark) {
  const ta = getTextarea()
  if (!ta) return
  const start = ta.selectionStart
  const value = props.modelValue
  const lineStart = value.lastIndexOf('\n', start - 1) + 1
  const next = value.slice(0, lineStart) + mark + value.slice(lineStart)
  emit('update:modelValue', next)
}

async function doUpload({ file }) {
  try {
    const res = await uploadFile(file)
    insert(`\n![图片](${res.url})\n`)
  } catch (e) {
    // 拦截器已提示
  }
}
</script>

<style scoped>
.md-editor {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
.md-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 8px;
  background: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
}
.md-panes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  min-height: v-bind(height);
}
.md-panes :deep(.el-textarea__inner) {
  border: none;
  border-radius: 0;
  box-shadow: none;
  min-height: v-bind(height);
}
.md-preview {
  border-left: 1px solid #e5e7eb;
  padding: 12px;
  max-height: v-bind(height);
  min-height: v-bind(height);
  overflow-y: auto;
  background: #fff;
}
</style>
