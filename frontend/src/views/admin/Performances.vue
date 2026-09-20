<template>
  <div>
    <div class="toolbar">
      <el-select
        v-model="ptype"
        placeholder="全部类型"
        clearable
        style="width: 140px"
        @change="reload"
      >
        <el-option label="积极" value="积极" />
        <el-option label="消极" value="消极" />
      </el-select>
      <StudentSelect
        v-model="studentId"
        v-model:class-id="classId"
        show-class-filter
        placeholder="按学生筛选"
        style="width: 320px"
        @update:model-value="reload"
        @update:class-id="reload"
      />
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">新增表现记录</el-button>
    </div>

    <!--
      积分汇总：与下方列表同源同筛选（都走 buildParams 的同一批 ref）。
      补上「积分看不到合计」的缺口 —— 表现是模块名，积分是它的数值维度，两者本就是一件事。
    -->
    <div class="page-card point-summary">
      <div class="ps-item">
        <span class="ps-value" :style="{ color: deltaColor }">{{ signed(summary.delta) }}</span>
        <span class="ps-label">积分变动</span>
      </div>
      <div class="ps-item">
        <span class="ps-value" style="color: #67c23a">{{ signed(summary.positive) }}</span>
        <span class="ps-label">累计加分</span>
      </div>
      <div class="ps-item">
        <span class="ps-value" style="color: #f56c6c">{{ summary.negative }}</span>
        <span class="ps-label">累计扣分</span>
      </div>
      <div class="ps-item">
        <span class="ps-value">{{ summary.count }}</span>
        <span class="ps-label">记录条数</span>
      </div>
      <div class="ps-item">
        <span class="ps-value">{{ summary.student_count }}</span>
        <span class="ps-label">涉及学生</span>
      </div>
    </div>

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="6"
        empty-description="暂无表现记录"
        @retry="load"
      >
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column label="学生" width="130">
            <template #default="{ row }">
              <el-link type="primary" :underline="false" @click="openStudentCard(row)">{{
                row.student_name
              }}</el-link>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="row.ptype === '积极' ? 'success' : 'danger'" size="small">{{
                row.ptype
              }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="积分" width="70" align="center">
            <template #default="{ row }">
              <span
                :style="{
                  color:
                    (row.points || 0) > 0
                      ? '#67c23a'
                      : (row.points || 0) < 0
                        ? '#f56c6c'
                        : '#909399',
                  fontWeight: 600,
                }"
              >
                {{ (row.points || 0) > 0 ? '+' + (row.points || 0) : row.points || 0 }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="content" label="内容" min-width="260" />
          <el-table-column prop="created_at" label="时间" width="170" />
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </StateView>
      <PaginationBar
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="total"
        @change="load"
      />
    </div>

    <el-dialog v-model="dialog" title="新增表现记录" width="460px">
      <el-form label-width="80px">
        <el-form-item label="学生" required
          ><StudentSelect v-model="form.student_id" show-class-filter
        /></el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.ptype" @change="onPtypeChange">
            <el-radio value="积极">积极（加分）</el-radio>
            <el-radio value="消极">消极（减分）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="积分">
          <el-input-number v-model="form.points" :min="-100" :max="100" />
          <span style="margin-left: 8px; color: #909399; font-size: 12px">正数加分，负数减分</span>
        </el-form-item>
        <el-form-item label="内容"
          ><el-input v-model="form.content" type="textarea" :rows="3"
        /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <StudentCard v-model:visible="studentCardVisible" :student-id="studentCardId" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import StudentSelect from '../../components/StudentSelect.vue'
import SortBar from '../../components/SortBar.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import StudentCard from '../../components/StudentCard.vue'
import StateView from '../../components/StateView.vue'
import { useSort } from '../../composables/useSort'
import { useCrudList } from '../../composables/useCrudList'
import { performanceApi } from '../../api'

const ptype = ref('')
const studentId = ref(null)
const classId = ref(null)
const dialog = ref(false)
const saving = ref(false)
const form = reactive({ student_id: null, ptype: '积极', content: '', points: 1 })

// 列表取数 / 分页 / 删除：统一由 useCrudList 提供，本页只描述差异（查询参数与删除文案）
const {
  items: rawItems,
  page,
  pageSize,
  total,
  loading,
  error,
  load,
  reload,
  remove,
} = useCrudList(performanceApi.list, {
  removeApi: performanceApi.remove,
  buildParams: () => ({
    ptype: ptype.value,
    student_id: studentId.value,
    class_id: classId.value,
  }),
  removeTip: () => '确定删除该记录吗？',
  // 列表每次加载成功后同步刷新积分汇总；删除记录走的也是 load()，因此汇总会自动跟着变
  onLoaded: loadSummary,
})

// ---------------- 积分汇总 ----------------
// 与列表共用同一批筛选 ref，保证「看到的记录」和「统计到的积分」永远是同一批数据
const EMPTY_SUMMARY = { delta: 0, positive: 0, negative: 0, count: 0, student_count: 0 }
const summary = ref({ ...EMPTY_SUMMARY })

async function loadSummary() {
  try {
    summary.value = await performanceApi.summary({
      student_id: studentId.value,
      class_id: classId.value,
      ptype: ptype.value,
    })
  } catch (e) {
    summary.value = { ...EMPTY_SUMMARY }
  }
}

/** 正数补 + 号，负号由数值自带 —— 让「加分/扣分」一眼可辨 */
function signed(v) {
  const n = v || 0
  return n > 0 ? `+${n}` : `${n}`
}

const deltaColor = computed(() => {
  const d = summary.value.delta || 0
  if (d > 0) return '#67c23a'
  if (d < 0) return '#f56c6c'
  return '#909399'
})

// 跨模块学生卡片
const studentCardVisible = ref(false)
const studentCardId = ref(null)
function openStudentCard(row) {
  if (!row.student_id) return
  studentCardId.value = row.student_id
  studentCardVisible.value = true
}

function onPtypeChange(val) {
  // 切换类型时自动调整积分正负
  form.points = val === '积极' ? Math.abs(form.points) : -Math.abs(form.points)
}

const { order, useSorted } = useSort('performances')
const items = useSorted(rawItems)

onMounted(load)

function openCreate() {
  Object.assign(form, { student_id: null, ptype: '积极', content: '', points: 1 })
  dialog.value = true
}

async function save() {
  if (!form.student_id) return ElMessage.warning('请选择学生')
  saving.value = true
  try {
    await performanceApi.create(form)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
/* 积分汇总条：横向排布 + 等宽数字，避免数值跳动时布局抖动 */
.point-summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 32px;
}
.ps-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.ps-value {
  font-size: 20px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.ps-label {
  font-size: 12px;
  color: #909399;
}
</style>
