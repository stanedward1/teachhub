<template>
  <div>
    <el-tabs v-model="activeTab">
      <!-- 成绩列表 -->
      <el-tab-pane label="成绩列表" name="list">
        <div class="toolbar">
          <el-input
            v-model="subject"
            placeholder="按科目筛选"
            clearable
            style="width: 180px"
            @clear="reload"
          />
          <StudentSelect
            v-model="studentId"
            v-model:class-id="classId"
            show-class-filter
            placeholder="按学生筛选"
            style="width: 320px"
            @update:model-value="reload"
            @update:class-id="reload"
          />
          <el-button @click="reload">查询</el-button>
          <div class="spacer"></div>
          <el-button @click="downloadTemplate">下载模板</el-button>
          <el-button type="success" @click="importDialog = true">批量导入</el-button>
          <el-button @click="exportExcel">导出成绩单</el-button>
          <el-button type="primary" @click="openCreate">录入成绩</el-button>
          <SortBar v-model="order" />
        </div>

        <div class="page-card">
          <StateView
            :loading="loading"
            :error="error"
            :empty="!items.length"
            :columns="6"
            empty-description="暂无成绩记录"
            @retry="load"
          >
            <template #empty>
              <el-button type="primary" @click="openCreate">录入第一条成绩</el-button>
            </template>
            <el-table :data="items" v-loading="loading" style="width: 100%">
              <el-table-column label="学生" width="120">
                <template #default="{ row }">
                  <el-link type="primary" :underline="false" @click="openStudentCard(row)">{{
                    row.student_name
                  }}</el-link>
                </template>
              </el-table-column>
              <el-table-column prop="student_no" label="学号" width="120" />
              <el-table-column prop="subject" label="科目" width="160" />
              <el-table-column prop="score" label="成绩" width="100" />
              <el-table-column prop="exam_name" label="考试名称" width="140" />
              <el-table-column label="操作" width="140" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
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
      </el-tab-pane>

      <!-- 成绩分析 -->
      <el-tab-pane label="成绩分析" name="analysis">
        <ScoreAnalysis :active="activeTab === 'analysis'" />
      </el-tab-pane>
    </el-tabs>

    <!-- 跨模块学生卡片 -->
    <StudentCard v-model:visible="studentCardVisible" :student-id="studentCardId" />

    <!-- 成绩录入 / 编辑 -->
    <ScoreFormDialog v-model="dialog" :score="editing" @saved="load" />

    <!-- 批量导入成绩 -->
    <ImportDialog
      v-model="importDialog"
      title="批量导入成绩"
      import-type="score"
      :import-fn="(fd) => scoreApi.import(fd)"
      :template-url="() => scoreApi.template()"
      template-filename="成绩导入模板.xlsx"
      @success="load"
    />
  </div>
</template>

<script setup>
/**
 * 成绩管理编排层。
 *
 * 由原 471 行的单文件拆分为「编排层 + 2 个子组件」：
 *  - 「成绩列表」页签与跨模块学生卡片保留在本文件；
 *  - 录入/编辑弹窗 → ./scores/ScoreFormDialog.vue；
 *  - 成绩分析页签（含排名表与趋势弹窗）→ ./scores/ScoreAnalysis.vue；
 *  - 批量导入弹窗 → 复用公共件 ../../components/ImportDialog.vue；
 *  - Excel 下载 → 复用公共件 ../../composables/useDownload.js。
 * 纯结构重构，对外行为（接口调用、文案、刷新时机、列顺序与宽度）完全等价。
 */
import { ref, onMounted } from 'vue'
import StudentSelect from '../../components/StudentSelect.vue'
import SortBar from '../../components/SortBar.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import StudentCard from '../../components/StudentCard.vue'
import ImportDialog from '../../components/ImportDialog.vue'
import StateView from '../../components/StateView.vue'
import ScoreFormDialog from './scores/ScoreFormDialog.vue'
import ScoreAnalysis from './scores/ScoreAnalysis.vue'
import { useSort } from '../../composables/useSort.js'
import { useCrudList } from '../../composables/useCrudList.js'
import { downloadExcel } from '../../composables/useDownload.js'
import { scoreApi } from '../../api'

const activeTab = ref('list')

const { order, useSorted } = useSort('scores')
const subject = ref('')
const studentId = ref(null)
const classId = ref(null)
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
} = useCrudList(scoreApi.list, {
  removeApi: scoreApi.remove,
  buildParams: () => ({
    subject: subject.value,
    student_id: studentId.value,
    class_id: classId.value,
  }),
  removeTip: () => '确定删除该成绩记录吗？',
})
const items = useSorted(rawItems)
const dialog = ref(false)
const editing = ref(null)

// 跨模块学生卡片
const studentCardVisible = ref(false)
const studentCardId = ref(null)
function openStudentCard(row) {
  if (!row.student_id) return
  studentCardId.value = row.student_id
  studentCardVisible.value = true
}

// 批量导入
const importDialog = ref(false)

onMounted(load)

function openCreate() {
  editing.value = null
  dialog.value = true
}

function openEdit(row) {
  editing.value = row
  dialog.value = true
}

async function exportExcel() {
  const res = await scoreApi.export({ student_id: studentId.value, class_id: classId.value })
  downloadExcel(res, '成绩单.xlsx')
}

// 批量导入
function downloadTemplate() {
  scoreApi.template().then((res) => {
    downloadExcel(res, '成绩导入模板.xlsx')
  })
}
</script>
