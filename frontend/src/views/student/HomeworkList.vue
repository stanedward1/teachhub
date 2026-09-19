<template>
  <div>
    <h2 class="page-title">我的作业</h2>
    <p class="page-subtitle">查看老师布置的上机任务，按时提交你的作业</p>

    <StateView
      :loading="loading"
      :error="error"
      :empty="!items.length"
      :rows="5"
      :columns="3"
      empty-description="暂无作业任务"
      @retry="load"
    >
      <div class="grid">
        <el-card v-for="a in items" :key="a.id" class="hw-card" shadow="hover" @click="go(a.id)">
          <div class="hw-head">
            <h3>{{ a.title }}</h3>
            <el-tag :type="a.my_submitted ? 'success' : 'warning'" size="small">
              {{ a.my_submitted ? '已提交' : '待提交' }}
            </el-tag>
          </div>
          <p class="hw-desc">{{ a.description || '暂无描述' }}</p>
          <div class="hw-meta">
            <span
              ><el-icon><User /></el-icon> {{ a.creator_name }}</span
            >
            <span
              ><el-icon><CollectionTag /></el-icon> {{ a.class_name }}</span
            >
            <span
              ><el-icon><Clock /></el-icon> 截止 {{ a.deadline || '不限' }}</span
            >
          </div>
        </el-card>
      </div>
    </StateView>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import StateView from '../../components/StateView.vue'
import { homeworkApi } from '../../api'

const router = useRouter()
const items = ref([])
const loading = ref(true)
const error = ref(false)

async function load() {
  loading.value = true
  error.value = false
  try {
    const res = await homeworkApi.assignments()
    items.value = res.items
  } catch (e) {
    error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)

function go(id) {
  router.push(`/homework/${id}`)
}
</script>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.hw-card {
  cursor: pointer;
  border-radius: 12px;
}
.hw-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}
.hw-head h3 {
  margin: 0;
  font-size: 16px;
  color: #111827;
}
.hw-desc {
  color: #6b7280;
  font-size: 13px;
  min-height: 40px;
  margin: 8px 0;
}
.hw-meta {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  color: #9ca3af;
  font-size: 12px;
}
.hw-meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.empty {
  text-align: center;
  color: #9ca3af;
  padding: 60px 0;
}
</style>
