<template>
  <el-dialog
    :model-value="modelValue"
    :title="`住宿状态记录 - ${student?.name || ''}`"
    width="620px"
    @update:model-value="(v) => emit('update:modelValue', v)"
  >
    <div v-loading="boardLoading">
      <template v-if="boardData">
        <!-- 当前状态 -->
        <div class="board-current">
          <span class="board-current-label">当前状态</span>
          <el-tag :type="boardData.current.type === 'day' ? 'info' : 'warning'" size="large">
            {{ boardData.current.label }}
          </el-tag>
          <span class="board-current-since">自 {{ boardData.current.since }} 起</span>
        </div>

        <!-- 各时间段（含起始/结束时间） -->
        <div class="board-section-title">住宿时间段历史</div>
        <el-table :data="boardData.periods" size="small" style="width: 100%">
          <el-table-column label="住宿类型" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="row.type === 'day' ? 'info' : 'warning'">{{
                row.label
              }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="起始时间" min-width="160">
            <template #default="{ row }">{{ row.start || '—' }}</template>
          </el-table-column>
          <el-table-column label="结束时间" min-width="160">
            <template #default="{ row }">
              <span
                :style="{ color: row.end ? '#374151' : '#2563eb', fontWeight: row.end ? 400 : 600 }"
              >
                {{ row.end || '至今' }}
              </span>
            </template>
          </el-table-column>
        </el-table>

        <!-- 变更日志 -->
        <template v-if="boardData.items.length">
          <div class="board-section-title">状态变更记录</div>
          <el-timeline>
            <el-timeline-item
              v-for="h in boardData.items"
              :key="h.id"
              :timestamp="h.changed_at || h.created_at"
            >
              <el-tag :type="h.old_type === 'day' ? 'info' : 'warning'" size="small">{{
                h.old_label
              }}</el-tag>
              <el-icon style="margin: 0 6px; vertical-align: middle"><Right /></el-icon>
              <el-tag :type="h.new_type === 'day' ? 'info' : 'warning'" size="small">{{
                h.new_label
              }}</el-tag>
              <span
                v-if="h.changed_by_name"
                style="color: #9ca3af; font-size: 12px; margin-left: 8px"
              >
                操作人：{{ h.changed_by_name }}
              </span>
            </el-timeline-item>
          </el-timeline>
        </template>
        <div v-else class="empty-state" style="padding: 12px 0">暂无状态变更记录</div>
      </template>
    </div>
  </el-dialog>
</template>

<script setup>
/**
 * 住宿状态记录弹窗。
 *
 * 从 Students.vue 原样搬出：展示当前住宿状态、住宿时间段历史与状态变更记录时间线。
 * 取数逻辑由父组件下沉到本组件——打开弹窗时（watch modelValue）请求学生住宿历史，
 * 请求与渲染时序、加载态与错误处理均与原父组件保持一致。
 */
import { ref, watch } from 'vue'
import { studentApi } from '../../../api'

const props = defineProps({
  /** 弹窗显隐（v-model） */
  modelValue: { type: Boolean, default: false },
  /** 目标学生 */
  student: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue'])

const boardLoading = ref(false)
const boardData = ref(null)

// 打开弹窗时加载住宿状态记录（每次打开都重新拉取）。
watch(
  () => props.modelValue,
  async (v) => {
    if (!v) return
    boardData.value = null
    boardLoading.value = true
    try {
      boardData.value = await studentApi.boardHistory(props.student.id)
    } catch (e) {
      console.error('[BoardHistoryDialog] 加载住宿状态记录失败:', e)
    } finally {
      boardLoading.value = false
    }
  }
)
</script>

<style scoped>
/* 寄宿/通学状态动态展示 */
.board-current {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: linear-gradient(135deg, #eff6ff, #f5f3ff);
  border-radius: 10px;
  margin-bottom: 16px;
}
.board-current-label {
  color: #6b7280;
  font-size: 13px;
}
.board-current-since {
  color: #6b7280;
  font-size: 13px;
  margin-left: 4px;
}
.board-section-title {
  font-weight: 600;
  font-size: 14px;
  color: #111827;
  margin: 16px 0 10px;
}
</style>
