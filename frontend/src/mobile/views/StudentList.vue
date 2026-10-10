<template>
  <div class="m-students">
    <van-search v-model="keyword" placeholder="搜索姓名 / 学号" @search="load" @clear="load" />
    <van-pull-refresh v-model="refreshing" @refresh="load">
      <van-cell-group inset>
        <van-cell
          v-for="s in items"
          :key="s.id"
          :title="s.name"
          :label="`${s.student_no} · ${s.class_name || '未分班'}`"
          is-link
          @click="$router.push(`/m/students/${s.id}`)"
        >
          <template #icon>
            <div class="m-stu-avatar">{{ s.name?.[0] }}</div>
          </template>
          <template #value>
            <van-tag :type="s.student_type === 'day' ? 'primary' : 'warning'" plain size="small">
              {{ s.student_type === 'day' ? '通学生' : '寄宿生' }}
            </van-tag>
          </template>
        </van-cell>
      </van-cell-group>
      <van-empty v-if="!loading && items.length === 0" description="未找到学生" />
    </van-pull-refresh>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useDebouncedRef } from '../../composables/useDebouncedRef'
import { mobileApi } from '../api/mobile'

const keyword = useDebouncedRef('', 300)
watch(keyword, () => load())
const items = ref([])
const loading = ref(false)
const refreshing = ref(false)
// 竞态守卫：搜索/下拉刷新并发在途时，旧响应晚到不覆盖新数据
let loadSeq = 0

async function load() {
  const seq = ++loadSeq
  loading.value = true
  try {
    const res = await mobileApi.students({ keyword: keyword.value })
    if (seq !== loadSeq) return
    items.value = res.items || []
  } catch (e) {
  } finally {
    if (seq === loadSeq) {
      loading.value = false
      refreshing.value = false
    }
  }
}

onMounted(load)
</script>

<style scoped>
.m-students {
  padding-bottom: 12px;
}
.m-stu-avatar {
  width: 40px;
  height: 40px;
  line-height: 40px;
  text-align: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  font-weight: 600;
  margin-right: 12px;
}
</style>
