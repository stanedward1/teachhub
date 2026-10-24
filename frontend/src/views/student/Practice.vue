<template>
  <div>
    <h2 class="page-title">学习资源</h2>
    <p class="page-subtitle">编程、打字、图文新闻与科普，按类别整理，一站直达</p>

    <StateView
      :loading="loading"
      :error="error"
      :empty="!groups.length"
      empty-description="暂无学习资源"
      error-description="资源加载失败，请稍后重试"
      @retry="load"
    >
      <!-- 卡片页不用表格骨架，给一块卡片形状的占位即可 -->
      <template #skeleton>
        <div class="skeleton-list">
          <div v-for="i in 3" :key="i" class="skeleton-card" />
        </div>
      </template>

      <!-- 单列分组：每类占满整行，组内链接横向铺开。
           不用 el-row/el-col 两列，是因为各分组条数不同（5/3/2/6/2/2/2），
           两列时矮的一侧下方会空出一大块，第二行也被高的一侧顶下去。 -->
      <div class="group-list">
        <section v-for="g in groups" :key="g.key" class="page-card">
          <h3 class="sec-title">
            <el-icon class="sec-icon"><component :is="ICONS[g.key] || Monitor" /></el-icon>
            <span>{{ g.title }}</span>
            <span class="count">{{ g.links.length }}</span>
          </h3>
          <p v-if="g.note" class="sec-note">{{ g.note }}</p>
          <div class="link-list">
            <a
              v-for="l in g.links"
              :key="l.name + l.url"
              :href="l.url"
              target="_blank"
              rel="noopener noreferrer"
              class="link-item"
            >
              <div class="link-main">
                <div class="l-name">{{ l.name }}</div>
                <div v-if="l.desc" class="l-desc">{{ l.desc }}</div>
              </div>
              <el-icon class="l-arrow"><TopRight /></el-icon>
            </a>
          </div>
        </section>
      </div>
    </StateView>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  EditPen,
  Memo,
  Monitor,
  Picture,
  Reading,
  School,
  TrendCharts,
} from '@element-plus/icons-vue'
import StateView from '../../components/StateView.vue'
import { metaApi } from '../../api'

/**
 * 分组图标按 key 映射。
 *
 * 后端 `meta_service.PRACTICE_DATA` 只下发教学语义（key / title / note / links），
 * 不返回图标名 —— 图标属于展示层，放在这里可以让后端不承担 UI 细节；
 * 新增分组时后端不用改，前端补一条映射即可（缺映射时回落 Monitor，不会渲染空白）。
 */
const ICONS = {
  coding: Monitor,
  tutorial: Reading,
  typing: EditPen,
  news: Picture,
  law: Memo,
  science: TrendCharts,
  career: School,
}

const groups = ref([])
const loading = ref(true)
const error = ref(false)

onMounted(load)

async function load() {
  loading.value = true
  error.value = false
  try {
    const data = await metaApi.practice()
    groups.value = data.groups || []
  } catch (e) {
    console.error('[Practice] 加载学习资源失败:', e)
    error.value = true
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.sec-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 4px;
  color: #111827;
  font-size: 16px;
}
.sec-icon {
  color: #2563eb;
}
/* 每类条数：让学生一眼判断这栏值不值得点开 */
.count {
  margin-left: auto;
  font-size: 12px;
  font-weight: 400;
  color: #9ca3af;
  background: #f3f4f6;
  border-radius: 999px;
  padding: 1px 8px;
}
.sec-note {
  margin: 0 0 12px;
  font-size: 12px;
  color: #9ca3af;
}
/* 组内链接横向铺开：单列分组 + 自适应列数，宽屏一屏能看到整类资源，
   既不会像两列布局那样在矮的一侧留白，也不会把页面拉得很长。
   用 auto-fit（而非 auto-fill）：条目不足整行时折叠空轨道让现有卡片撑满，
   避免每类最后一行右侧空出一格。 */
.link-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 10px;
}
.link-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #eef1f6;
  border-radius: 10px;
  text-decoration: none;
  color: inherit;
  transition: all 0.2s;
}
.link-item:hover {
  border-color: #2563eb;
  background: #eff6ff;
}
/* 站点名过长（如「国家职业教育智慧教育平台」）时换行，不撑破卡片 */
.link-main {
  min-width: 0;
}
.l-name {
  font-weight: 600;
  color: #111827;
}
.l-desc {
  font-size: 13px;
  color: #6b7280;
  margin-top: 2px;
}
.l-arrow {
  color: #9ca3af;
  flex-shrink: 0;
}
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.skeleton-card {
  height: 150px;
  border-radius: 12px;
  background: linear-gradient(90deg, #f3f4f6, #e5e7eb, #f3f4f6);
  background-size: 200% 100%;
  animation: shimmer 1.2s infinite;
}
@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
/* 窄屏组内退化为单列，链接仍是横向可点的大目标 */
@media (max-width: 640px) {
  .link-list {
    grid-template-columns: 1fr;
  }
}
</style>
