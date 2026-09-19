<template>
  <div class="brand" @click="router.push('/admin/dashboard')">
    <span class="brand-mark">T</span>
    <transition name="fade">
      <span v-if="!collapsed" class="brand-text">TeachHub</span>
    </transition>
  </div>

  <el-menu
    :default-active="activeMenu"
    :collapse="collapsed"
    :collapse-transition="false"
    router
    class="menu"
    background-color="transparent"
    text-color="rgba(255,255,255,0.65)"
    active-text-color="#fff"
    @select="$emit('select')"
  >
    <template v-for="item in items" :key="item.key || item.index">
      <el-sub-menu v-if="item.children" :index="item.key">
        <template #title>
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </template>
        <el-menu-item v-for="leaf in item.children" :key="leaf.index" :index="leaf.index">
          {{ leaf.label }}
        </el-menu-item>
      </el-sub-menu>

      <el-menu-item v-else :index="item.index">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </el-menu-item>
    </template>
  </el-menu>

  <!-- 折叠按钮 -->
  <div class="collapse-btn" @click="toggleCollapsed">
    <el-icon><component :is="collapsed ? 'Expand' : 'Fold'" /></el-icon>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({
  /** 侧边栏是否折叠。 */
  collapsed: { type: Boolean, default: false },
  /** 已按角色过滤好的菜单树。 */
  items: { type: Array, default: () => [] },
  /** 当前激活的菜单 index。 */
  activeMenu: { type: String, default: '' },
})

const emit = defineEmits(['update:collapsed', 'select'])

const router = useRouter()

/** 切换折叠状态（通过 v-model:collapsed 交回父组件处理）。 */
function toggleCollapsed() {
  emit('update:collapsed', !props.collapsed)
}
</script>

<style scoped>
.brand {
  height: 60px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  cursor: pointer;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.brand-mark {
  width: 32px;
  height: 32px;
  min-width: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 15px;
}

.brand-text {
  font-weight: 700;
  font-size: 16px;
  color: #fff;
  white-space: nowrap;
  letter-spacing: -0.01em;
}

/* 菜单 */
.menu {
  border-right: none !important;
  flex: 1;
  padding: 8px;
  overflow-y: auto;
  overflow-x: hidden;
}

.menu :deep(.el-menu-item),
.menu :deep(.el-sub-menu__title) {
  border-radius: 8px;
  margin: 2px 0;
  height: 40px;
  line-height: 40px;
  font-size: 13px;
  transition: all 0.15s ease;
}

.menu :deep(.el-menu-item:hover),
.menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
}

.menu :deep(.el-menu-item.is-active) {
  background: var(--brand);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.35);
}

/* 子菜单展开背景 */
.menu :deep(.el-menu) {
  background: rgba(0, 0, 0, 0.15) !important;
  border-radius: 6px;
  margin: 2px 4px;
}

.menu :deep(.el-menu .el-menu-item) {
  padding-left: 56px !important;
  font-size: 13px;
  height: 36px;
  line-height: 36px;
}

.menu :deep(.el-menu .el-menu-item.is-active) {
  background: var(--brand);
}

/* 折叠模式 */
.menu.el-menu--collapse {
  padding: 8px 4px;
  width: 64px;
}

.menu.el-menu--collapse :deep(.el-menu-item),
.menu.el-menu--collapse :deep(.el-sub-menu__title) {
  padding: 0 !important;
  justify-content: center;
}

.menu.el-menu--collapse :deep(.el-sub-menu__title) .el-icon {
  margin: 0;
}

/* 折叠按钮 */
.collapse-btn {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.4);
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
  transition: color 0.15s;
  font-size: 18px;
}

.collapse-btn:hover {
  color: rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.04);
}

/* 过渡动画：作用于品牌文字（.brand-text），随该元素一并迁入本组件 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 1024px) {
  .brand-text {
    display: none;
  }
  .collapse-btn {
    display: none;
  }
  .menu {
    padding: 8px 4px;
  }
  .menu :deep(.el-menu-item),
  .menu :deep(.el-sub-menu__title) {
    padding: 0 !important;
    justify-content: center;
  }
  .menu :deep(.el-sub-menu__title) .el-icon {
    margin: 0;
  }
}

@media (max-width: 768px) {
  .collapse-btn {
    display: none !important;
  }
}
</style>
