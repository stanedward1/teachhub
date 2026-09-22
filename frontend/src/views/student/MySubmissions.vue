<template>
  <div>
    <h2 class="page-title">我的提交</h2>
    <p class="page-subtitle">查看你提交过的所有作业</p>

    <StateView
      :loading="loading"
      :error="error"
      :empty="!items.length"
      :columns="6"
      empty-description="暂无提交记录"
      @retry="load"
    >
      <el-table :data="items" v-loading="loading" style="width: 100%">
        <el-table-column prop="assignment_title" label="作业任务" min-width="200" />
        <el-table-column label="内容预览" min-width="240">
          <template #default="{ row }">{{ (row.content || '').slice(0, 60) || '—' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="180" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.is_excellent ? 'success' : 'info'" size="small">
              {{ row.is_excellent ? '优秀作品' : '已提交' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="AI 批改" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.ai_grading_status === 'success'" type="success" size="small">已批改</el-tag>
            <el-tag v-else-if="row.ai_grading_status === 'pending'" type="warning" size="small">批改中</el-tag>
            <el-tag v-else-if="row.ai_grading_status === 'failed'" type="info" size="small">未完成</el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="goDetail(row.id)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
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

function goDetail(id) {
  router.push(`/my-submissions/${id}`)
}

async function load() {
  loading.value = true
  error.value = false
  try {
    const res = await homeworkApi.mySubmissions()
    items.value = res.items
  } catch (e) {
    error.value = true
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.empty {
  text-align: center;
  color: #9ca3af;
  padding: 40px 0;
}
.muted {
  color: #9ca3af;
}
</style>
