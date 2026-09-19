<template>
  <div class="m-record">
    <van-tabs v-model:active="activeTab">
      <van-tab title="记表现" name="performance" />
      <van-tab title="记谈心" name="talk" />
    </van-tabs>

    <!-- 选择学生 -->
    <van-cell-group inset style="margin-top: 12px">
      <van-field
        :model-value="studentName"
        readonly
        is-link
        label="学生"
        placeholder="点击选择学生"
        @click="showPicker = true"
      />
    </van-cell-group>

    <!-- 表现类型 -->
    <van-cell-group inset v-if="activeTab === 'performance'">
      <van-field name="ptype" label="类型">
        <template #input>
          <van-radio-group v-model="ptype" direction="horizontal">
            <van-radio name="积极">积极</van-radio>
            <van-radio name="消极">消极</van-radio>
          </van-radio-group>
        </template>
      </van-field>
    </van-cell-group>

    <!-- 内容 -->
    <van-cell-group inset>
      <van-field
        v-model="content"
        type="textarea"
        rows="4"
        autosize
        maxlength="500"
        :placeholder="
          activeTab === 'performance' ? '记录表现内容，如：课堂积极回答问题' : '记录谈心内容'
        "
        show-word-limit
      />
    </van-cell-group>

    <div style="margin: 16px">
      <van-button round block type="primary" :loading="saving" @click="submit">提交</van-button>
    </div>

    <!-- 学生选择弹窗 -->
    <van-popup v-model:show="showPicker" position="bottom" :style="{ height: '80%' }">
      <div class="m-picker">
        <van-search v-model="pickKeyword" placeholder="搜索学生" @search="loadPicker" />
        <!-- 学生是全校长列表（可能上千条），用虚拟滚动只渲染可视区域，避免弹窗卡顿 -->
        <VirtualList :items="pickList" :item-height="64" :height="pickerHeight">
          <template #default="{ item: s }">
            <van-cell
              :title="s.name"
              :label="`${s.student_no} · ${s.class_name || ''}`"
              @click="chooseStudent(s)"
            />
          </template>
        </VirtualList>
        <van-empty v-if="!pickList.length" description="未找到学生" />
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { showToast, showSuccessToast } from 'vant'
import { mobileApi } from '../api/mobile'
import { performanceApi, talkApi } from '../../api'
import VirtualList from '../../components/VirtualList.vue'

const route = useRoute()
const activeTab = ref(route.query.type === 'talk' ? 'talk' : 'performance')
const studentId = ref(null)
const studentName = ref('')
const ptype = ref('积极')
const content = ref('')
const saving = ref(false)

const showPicker = ref(false)
const pickKeyword = ref('')
const pickList = ref([])

// 弹窗可视高度 = 80% 视口高 - 搜索栏高度，作为虚拟列表滚动容器高度
const pickerHeight = ref(420)

function syncPickerHeight() {
  const vh = window.innerHeight || 667
  pickerHeight.value = Math.max(200, Math.round(vh * 0.8) - 54)
}

async function loadPicker() {
  try {
    const res = await mobileApi.students({ keyword: pickKeyword.value })
    pickList.value = res.items || []
  } catch (e) {}
}

function chooseStudent(s) {
  studentId.value = s.id
  studentName.value = s.name
  showPicker.value = false
}

async function submit() {
  if (!studentId.value) return showToast('请选择学生')
  if (!content.value.trim()) return showToast('请填写内容')
  saving.value = true
  try {
    if (activeTab.value === 'performance') {
      await performanceApi.create({
        student_id: studentId.value,
        ptype: ptype.value,
        content: content.value.trim(),
      })
    } else {
      await talkApi.create({ student_id: studentId.value, content: content.value.trim() })
    }
    showSuccessToast('记录成功')
    content.value = ''
    studentId.value = null
    studentName.value = ''
  } catch (e) {
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  syncPickerHeight()
  window.addEventListener('resize', syncPickerHeight)
  loadPicker()
})

onBeforeUnmount(() => window.removeEventListener('resize', syncPickerHeight))
</script>

<style scoped>
.m-record {
  padding-bottom: 12px;
}
.m-picker {
  padding-bottom: 16px;
}
</style>
