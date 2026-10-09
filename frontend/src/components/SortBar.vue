<template>
  <el-button-group class="sort-bar">
    <el-button
      :type="modelValue === 'desc' ? 'primary' : ''"
      size="small"
      @click="$emit('update:modelValue', 'desc')"
    >
      <el-icon><SortDown /></el-icon>
      最新在前
    </el-button>
    <el-button
      :type="modelValue === 'asc' ? 'primary' : ''"
      size="small"
      @click="$emit('update:modelValue', 'asc')"
    >
      <el-icon><SortUp /></el-icon>
      最早在前
    </el-button>
  </el-button-group>
</template>

<script setup>
defineProps({
  modelValue: { type: String, default: 'desc' },
})
defineEmits(['update:modelValue'])
</script>

<style scoped>
.sort-bar {
  flex-shrink: 0;
}
</style>
