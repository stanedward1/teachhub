<template>
  <div class="pagination-bar">
    <span class="page-size-label">每页</span>
    <el-select
      :model-value="pageSize"
      size="small"
      style="width: 88px"
      @update:model-value="onSizeChange"
    >
      <el-option v-for="s in sizeOptions" :key="s" :label="`${s} 条`" :value="s" />
    </el-select>
    <el-pagination
      class="pagination-bar__pager"
      layout="total, prev, pager, next"
      :total="total"
      :page-size="pageSize"
      :current-page="page"
      @current-change="onPageChange"
    />
  </div>
</template>

<script setup>
defineProps({
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  sizeOptions: { type: Array, default: () => [20, 50, 100] }
})

const emit = defineEmits(['update:page', 'update:pageSize', 'change'])

function onPageChange(p) {
  emit('update:page', p)
  emit('change')
}

function onSizeChange(size) {
  emit('update:pageSize', size)
  emit('update:page', 1)
  emit('change')
}
</script>

<style scoped>
.pagination-bar {
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
.page-size-label {
  font-size: 13px;
  color: var(--text-tertiary);
}
.pagination-bar__pager {
  margin: 0;
}
</style>
