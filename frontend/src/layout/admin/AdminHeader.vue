<template>
  <div class="header-left">
    <el-icon class="mobile-menu-btn" @click="$emit('open-menu')"><Menu /></el-icon>
    <span class="header-breadcrumb">
      <template v-for="(part, i) in breadcrumb" :key="i">
        <span v-if="i > 0" class="breadcrumb-sep">/</span>
        <span :class="{ 'breadcrumb-current': i === breadcrumb.length - 1 }">{{ part }}</span>
      </template>
    </span>
  </div>

  <el-dropdown @command="$emit('command', $event)" trigger="click">
    <span class="user-chip">
      <el-avatar :size="32" :src="user?.avatar" class="user-avatar">
        {{ user?.name?.[0] }}
      </el-avatar>
      <span class="user-name">{{ user?.name }}</span>
      <el-tag size="small" effect="plain" type="info">{{ roleText }}</el-tag>
    </span>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="change-password">
          <el-icon><Key /></el-icon>
          修改密码
        </el-dropdown-item>
        <el-dropdown-item command="portal">
          <el-icon><Switch /></el-icon>
          学生端首页
        </el-dropdown-item>
        <el-dropdown-item command="logout" divided>
          <el-icon><Back /></el-icon>
          退出登录
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
defineProps({
  /** 面包屑文本数组。 */
  breadcrumb: { type: Array, default: () => [] },
  /** 当前登录用户，可为空。 */
  user: { type: Object, default: null },
  /** 角色展示文案。 */
  roleText: { type: String, default: '' },
})

defineEmits(['open-menu', 'command'])
</script>

<style scoped>
.header-left {
  display: flex;
  align-items: center;
}

.header-breadcrumb {
  font-size: 14px;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.breadcrumb-sep {
  color: #d1d5db;
  font-size: 12px;
}

.breadcrumb-current {
  color: var(--text-primary);
  font-weight: 600;
}

/* 用户区 */
.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
  padding: 4px 8px;
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.user-chip:hover {
  background: #f3f4f6;
}

.user-avatar {
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  font-weight: 600;
}

.user-name {
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
}

/* 默认隐藏移动端菜单按钮 */
.mobile-menu-btn {
  display: none;
}

@media (max-width: 768px) {
  .mobile-menu-btn {
    display: inline-flex;
    font-size: 20px;
    cursor: pointer;
    color: #4b5563;
    margin-right: 8px;
  }
  .user-name {
    display: none;
  }
}
</style>
