<template>
  <div class="m-leaves">
    <van-tabs v-model:active="statusTab" @change="load">
      <van-tab title="待销假" name="登记" />
      <van-tab title="已销假" name="已销假" />
      <van-tab title="全部" name="" />
    </van-tabs>

    <van-pull-refresh v-model="refreshing" @refresh="load">
      <van-cell-group inset style="margin-top: 12px">
        <van-cell
          v-for="l in items"
          :key="l.id"
          :title="l.student_name"
          :label="`${l.reason || '未填写'} · ${l.start_date || ''} ~ ${l.end_date || ''}`"
        >
          <template #value>
            <van-button
              v-if="l.status !== '已销假'"
              size="small"
              type="primary"
              plain
              @click.stop="approve(l)"
            >
              销假
            </van-button>
            <van-tag v-else type="success" size="small">已销假</van-tag>
          </template>
        </van-cell>
      </van-cell-group>
      <van-empty v-if="!loading && items.length === 0" description="暂无请假记录" />
    </van-pull-refresh>

    <!-- 浮动新增按钮 -->
    <div class="m-fab" @click="openCreate">
      <van-icon name="plus" size="22" />
    </div>

    <!-- 新增请假弹窗 -->
    <van-popup v-model:show="showCreate" position="bottom" round :style="{ height: '88%' }">
      <div class="m-create">
        <van-nav-bar title="新增请假" left-arrow @click-left="showCreate = false" />
        <van-cell-group inset>
          <van-field
            :model-value="form.student_name"
            readonly
            is-link
            label="学生"
            placeholder="选择学生"
            @click="showStudentPicker = true"
          />
          <van-field v-model="form.reason" label="事由" placeholder="如：感冒发烧" />
          <van-field
            :model-value="dateRangeText"
            readonly
            is-link
            label="请假时间"
            placeholder="选择开始和结束日期"
            @click="showCalendar = true"
          />
        </van-cell-group>
        <div style="margin: 16px">
          <van-button round block type="primary" :loading="saving" @click="submit">提交</van-button>
        </div>
      </div>
    </van-popup>

    <!-- 学生选择弹窗 -->
    <van-popup v-model:show="showStudentPicker" position="bottom" :style="{ height: '80%' }">
      <div class="m-picker">
        <van-search v-model="pickKeyword" placeholder="搜索学生" @search="loadPicker" />
        <van-cell
          v-for="s in pickList"
          :key="s.id"
          :title="s.name"
          :label="`${s.student_no} · ${s.class_name || ''}`"
          @click="chooseStudent(s)"
        />
        <van-empty v-if="!pickList.length" description="未找到学生" />
      </div>
    </van-popup>

    <!-- 日期范围选择 -->
    <van-calendar v-model:show="showCalendar" type="range" @confirm="onDateConfirm" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { showConfirmDialog, showSuccessToast, showToast } from 'vant'
import { leaveApi } from '../../api'
import { mobileApi } from '../api/mobile'

const statusTab = ref('登记')
const items = ref([])
const loading = ref(false)
const refreshing = ref(false)

// 新增请假
const showCreate = ref(false)
const saving = ref(false)
const form = reactive({
  student_id: null,
  student_name: '',
  reason: '',
  start_date: '',
  end_date: '',
})
const showStudentPicker = ref(false)
const pickKeyword = ref('')
const pickList = ref([])
const showCalendar = ref(false)

const dateRangeText = computed(() => {
  if (form.start_date && form.end_date) return `${form.start_date} ~ ${form.end_date}`
  return ''
})

async function load() {
  loading.value = true
  try {
    const res = await leaveApi.list({ status: statusTab.value, page_size: 100 })
    items.value = res.items || []
  } catch (e) {
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function approve(l) {
  try {
    await showConfirmDialog({ title: '销假确认', message: `确认为「${l.student_name}」办理销假？` })
  } catch {
    return
  }
  try {
    await leaveApi.update(l.id, { status: '已销假' })
    showSuccessToast('已销假')
    load()
  } catch (e) {}
}

function openCreate() {
  Object.assign(form, {
    student_id: null,
    student_name: '',
    reason: '',
    start_date: '',
    end_date: '',
  })
  showCreate.value = true
}

async function loadPicker() {
  try {
    const res = await mobileApi.students({ keyword: pickKeyword.value })
    pickList.value = res.items || []
  } catch (e) {}
}

function chooseStudent(s) {
  form.student_id = s.id
  form.student_name = s.name
  showStudentPicker.value = false
}

function onDateConfirm(dates) {
  if (dates && dates.length >= 2) {
    form.start_date = fmt(dates[0])
    form.end_date = fmt(dates[1])
  }
  showCalendar.value = false
}

function fmt(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

async function submit() {
  if (!form.student_id) return showToast('请选择学生')
  if (!form.reason.trim()) return showToast('请填写事由')
  if (!form.start_date || !form.end_date) return showToast('请选择请假时间')
  saving.value = true
  try {
    await leaveApi.create({
      student_id: form.student_id,
      reason: form.reason.trim(),
      start_date: form.start_date,
      end_date: form.end_date,
    })
    showSuccessToast('新增成功')
    showCreate.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.m-leaves {
  padding-bottom: 70px;
}
.m-fab {
  position: fixed;
  right: 20px;
  bottom: 80px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: #2563eb;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
  z-index: 10;
}
.m-picker {
  padding-bottom: 16px;
}
</style>
