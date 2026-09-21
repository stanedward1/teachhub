<template>
  <div>
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索姓名/学号"
        clearable
        style="width: 220px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-select
        v-model="classId"
        placeholder="全部班级"
        clearable
        style="width: 180px"
        @change="reload"
      >
        <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-select v-model="droppedFilter" style="width: 120px" @change="reload">
        <el-option label="在籍学生" value="false" />
        <el-option label="已退学" value="true" />
        <el-option label="全部" value="" />
      </el-select>
      <el-button @click="reload">查询</el-button>
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button @click="downloadTemplate">下载模板</el-button>
      <el-button type="success" @click="openImport">批量导入</el-button>
      <el-button @click="exportExcel">导出花名册</el-button>
      <el-button type="primary" @click="openCreate">添加学生</el-button>
    </div>

    <!-- 通学生/寄宿生人数对比图表 -->
    <BoardTypeChart v-if="classId" ref="chartRef" :class-id="classId" />

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="8"
        empty-description="暂无学生"
        @retry="load"
      >
        <template #empty>
          <el-button type="primary" @click="openCreate">添加学生</el-button>
          <el-button @click="openImport">批量导入</el-button>
        </template>
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="student_no" label="学号" width="120" />
          <el-table-column label="头像" width="70">
            <template #default="{ row }">
              <StudentAvatarCell :row="row" @updated="(v) => (row.avatar = v)" />
            </template>
          </el-table-column>
          <el-table-column prop="name" label="姓名" width="100" />
          <el-table-column prop="gender" label="性别" width="70" />
          <el-table-column prop="class_name" label="班级" width="160" />
          <el-table-column prop="major" label="专业" width="140" />
          <el-table-column prop="parent_name" label="家长姓名" width="100" />
          <el-table-column prop="parent_phone" label="家长电话" width="130" />
          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="row.student_type === 'day' ? 'info' : 'warning'"
                style="cursor: pointer"
                title="点击查看住宿状态变更历史"
                @click="openBoardHistory(row)"
              >
                {{ row.student_type === 'day' ? '通学生' : '寄宿生' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.is_dropped_out ? 'danger' : 'success'" size="small">
                {{ row.is_dropped_out ? '已退学' : '在籍' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" :disabled="row.is_dropped_out" @click="openEdit(row)"
                >编辑</el-button
              >
              <el-button
                link
                type="success"
                @click="$router.push(`/admin/students/${row.id}/profile`)"
                >画像</el-button
              >
              <el-button
                link
                type="warning"
                :disabled="row.is_dropped_out"
                @click="openPassword(row)"
                >密码</el-button
              >
              <el-button link type="danger" :disabled="row.is_dropped_out" @click="remove(row)"
                >删除</el-button
              >
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

    <StudentFormDialog
      v-model="formDialog"
      :classes="classes"
      :student="formStudent"
      :default-class-id="classId"
      @saved="load"
    />

    <StudentPasswordDialog v-model="pwdDialog" :student="pwdTarget" />

    <BoardHistoryDialog v-model="boardDialog" :student="boardStudent" />

    <ImportDialog
      v-model="importDialog"
      title="批量导入学生"
      :import-fn="(fd) => studentApi.import(fd)"
      :template-url="() => studentApi.template()"
      template-filename="学生导入模板.xlsx"
      @success="load"
    />
  </div>
</template>

<script setup>
/**
 * 学生管理页 —— 编排层。
 *
 * 原 663 行的巨型组件按职责拆分为「编排层 + 5 个子组件」：
 *  - StudentFormDialog     添加/编辑学生弹窗
 *  - StudentPasswordDialog 密码管理弹窗
 *  - BoardHistoryDialog    住宿状态记录弹窗
 *  - BoardTypeChart        通学生/寄宿生饼图 + 明细弹窗
 *  - StudentAvatarCell     表格头像上传单元格
 * 本层只保留工具栏、学生表格、分页与列表取数/增删逻辑，以及各子组件的编排调用。
 * 对外行为（接口调用、提示文案、字段名、刷新时机、按钮/列顺序与宽度）完全不变。
 */
import { ref, onMounted, watch } from 'vue'
import { useDebouncedRef } from '../../composables/useDebouncedRef'
import SortBar from '../../components/SortBar.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import ImportDialog from '../../components/ImportDialog.vue'
import StateView from '../../components/StateView.vue'
import { useSort } from '../../composables/useSort'
import { useCrudList } from '../../composables/useCrudList'
import { downloadExcel } from '../../composables/useDownload'
import { studentApi } from '../../api'
import StudentFormDialog from './students/StudentFormDialog.vue'
import StudentPasswordDialog from './students/StudentPasswordDialog.vue'
import BoardHistoryDialog from './students/BoardHistoryDialog.vue'
import BoardTypeChart from './students/BoardTypeChart.vue'
import StudentAvatarCell from './students/StudentAvatarCell.vue'

const classes = ref([])
const keyword = useDebouncedRef('', 300)
const classId = ref(null)
const droppedFilter = ref('false')

// 通学生/寄宿生图表
const chartRef = ref(null)

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
} = useCrudList(studentApi.list, {
  removeApi: studentApi.remove,
  buildParams: () => ({
    keyword: keyword.value,
    class_id: classId.value,
    dropped_out: droppedFilter.value,
  }),
  removeTip: (row) => `确定删除学生「${row.name}」吗？`,
  onLoaded: () => {
    // 数据加载完成后联动刷新通学生/寄宿生统计
    if (classId.value) chartRef.value?.reload()
  },
})

// 搜索条件变化必须重置页码：否则在第 3 页改关键词会拿新条件查旧页码，结果错乱
watch(keyword, reload)

// 学生表单弹窗
const formDialog = ref(false)
const formStudent = ref(null)

// 密码管理弹窗
const pwdDialog = ref(false)
const pwdTarget = ref(null)

// 寄宿/通学状态动态展示弹窗
const boardDialog = ref(false)
const boardStudent = ref(null)

// 批量导入弹窗
const importDialog = ref(false)

const { order, useSorted } = useSort('students')
const items = useSorted(rawItems)

onMounted(async () => {
  // 管理员看全部班级，教师只看自己负责的班级
  const res = await studentApi.classrooms()
  classes.value = res.items
  load()
})

function openCreate() {
  formStudent.value = null
  formDialog.value = true
}

function openEdit(row) {
  formStudent.value = row
  formDialog.value = true
}

async function exportExcel() {
  const droppedParam = droppedFilter.value === '' ? 'all' : droppedFilter.value
  const res = await studentApi.export({ class_id: classId.value, dropped_out: droppedParam })
  downloadExcel(res, '学生花名册.xlsx')
}

// 密码管理
function openPassword(row) {
  pwdTarget.value = row
  pwdDialog.value = true
}

// 寄宿/通学状态动态展示：打开弹窗（数据由弹窗自行加载）
function openBoardHistory(row) {
  boardStudent.value = row
  boardDialog.value = true
}

// 批量导入
function downloadTemplate() {
  studentApi.template().then((res) => downloadExcel(res, '学生导入模板.xlsx'))
}

function openImport() {
  importDialog.value = true
}
</script>
