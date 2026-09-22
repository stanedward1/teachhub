<template>
  <!-- AI 批改建议（学生口径：纯展示，不含模型名/推荐理由/附件等教师专属信息） -->
  <div v-if="ai" class="ai-panel">
    <div class="ai-head">
      <span class="ai-title">AI 批改建议</span>
      <el-tag size="small" :type="statusType">{{ statusText }}</el-tag>
      <el-tag v-if="ai.score != null" size="small" type="warning">{{ ai.score }} 分</el-tag>
    </div>
    <div class="ai-disclaimer">AI 生成，仅供参考，以教师评语为准</div>

    <template v-if="ai.status === 'success'">
      <div v-if="ai.summary" class="ai-block">
        <div class="ai-label">总评</div>
        <div class="ai-text">{{ ai.summary }}</div>
      </div>
      <div v-if="ai.strengths" class="ai-block">
        <div class="ai-label">亮点</div>
        <div class="ai-text">{{ ai.strengths }}</div>
      </div>
      <div v-if="ai.improvements" class="ai-block">
        <div class="ai-label">改进建议</div>
        <div class="ai-text">{{ ai.improvements }}</div>
      </div>
    </template>
    <div v-else-if="ai.status === 'pending'" class="ai-text ai-muted">批改中，请稍后刷新…</div>
    <div v-else class="ai-text ai-muted">暂无 AI 批改建议</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** AI 批改结果对象（后端 ai_grading 字段）；为 null 时整块不渲染 */
  ai: { type: Object, default: null },
})

// 批改状态文案（失败态不暴露内部原因）
const statusText = computed(() => {
  if (props.ai?.status === 'success') return '已批改'
  if (props.ai?.status === 'pending') return '批改中'
  return '未完成'
})

const statusType = computed(() => {
  if (props.ai?.status === 'success') return 'success'
  if (props.ai?.status === 'pending') return 'warning'
  return 'info'
})
</script>

<style scoped>
/* AI 批改区块：与教师点评（蓝色）区分，并显式标注「仅供参考」 */
.ai-panel {
  margin-top: 12px;
  padding: 12px 14px;
  background: #f5f3ff;
  border: 1px solid #ddd6fe;
  border-radius: 8px;
}
.ai-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.ai-title {
  font-size: 13px;
  font-weight: 600;
  color: #5b21b6;
}
.ai-disclaimer {
  font-size: 12px;
  color: #9ca3af;
  margin: 6px 0 8px;
}
.ai-block {
  margin-bottom: 8px;
}
.ai-label {
  font-size: 12px;
  font-weight: 600;
  color: #6d28d9;
  margin-bottom: 2px;
}
.ai-text {
  font-size: 14px;
  color: #374151;
  line-height: 1.7;
  white-space: pre-wrap;
}
.ai-muted {
  color: #9ca3af;
}
</style>
