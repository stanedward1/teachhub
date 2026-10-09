<template>
  <div>
    <el-page-header
      :content="assignment?.title || '提交审阅'"
      @back="$router.back()"
      style="margin-bottom: 16px"
    />

    <!-- 任务正文（Markdown 渲染） -->
    <div class="page-card" v-if="assignment?.content">
      <div style="font-weight: 500; margin-bottom: 12px; color: #303133">任务说明</div>
      <Markdown :content="assignment.content" />
    </div>

    <div class="page-card">
      <!-- 骨架屏占位列数按角色取值：教师含「学伴」列 = 7；管理员不渲染该列 = 6（与 :columns 一致） -->
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="canViewCompanion ? 7 : 6"
        empty-description="暂无提交记录"
        @retry="load"
      >
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="student_name" label="学生" width="120" />
          <el-table-column label="作业内容" min-width="300">
            <template #default="{ row }">
              <div class="content-preview" v-if="row.content">
                <Markdown :content="row.content" />
              </div>
              <span v-else style="color: #9ca3af">（仅上传附件）</span>
            </template>
          </el-table-column>
          <el-table-column prop="filename" label="附件" width="140">
            <template #default="{ row }">
              <a v-if="row.filepath" :href="'/uploads/' + row.filepath" target="_blank">{{
                row.filename || '下载'
              }}</a>
              <span v-else>—</span>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="提交时间" width="170" />
          <el-table-column label="AI 批改" width="110">
            <template #default="{ row }">
              <el-tag v-if="row.ai_grading_status === 'success'" size="small" type="success"
                >已批改</el-tag
              >
              <el-tag v-else-if="row.ai_grading_status === 'pending'" size="small" type="warning"
                >批改中</el-tag
              >
              <span v-else class="muted">未批改</span>
            </template>
          </el-table-column>
          <!-- 学伴：展示轮数 / 是否有拒答，点击打开只读会话面板（设计 §14.6）；
               教师专属接口，非教师角色不展示该列 -->
          <el-table-column v-if="canViewCompanion" label="学伴" width="130">
            <template #default="{ row }">
              <el-button
                v-if="companionOf(row)"
                link
                type="primary"
                @click="openCompanion(companionOf(row))"
              >
                {{ companionOf(row).turn_count }} 轮
                <el-tag
                  v-if="companionOf(row).has_refused"
                  size="small"
                  type="warning"
                  style="margin-left: 4px"
                  >拒答</el-tag
                >
              </el-button>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="row.is_excellent ? 'success' : 'info'" size="small">
                {{ row.is_excellent ? '优秀' : '普通' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="300" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetail(row)">查看详情</el-button>
              <el-button
                link
                type="primary"
                :loading="aiGradingId === row.id"
                :disabled="row.ai_grading_status === 'pending'"
                @click="aiGrade(row)"
                >{{ aiGradeText(row.ai_grading_status) }}</el-button
              >
              <el-button v-if="!row.is_excellent" link type="success" @click="mark(row)"
                >选为优秀</el-button
              >
              <el-button
                v-else
                link
                type="warning"
                :loading="unmarkingId === row.id"
                @click="unmark(row)"
                >取消优秀</el-button
              >
            </template>
          </el-table-column>
        </el-table>
      </StateView>
    </div>

    <!-- 提交列表分页（P1-3）：翻页 / 改每页条数由 PaginationBar 触发 load -->
    <PaginationBar v-model:page="page" v-model:page-size="pageSize" :total="total" @change="load" />

    <el-dialog v-model="dialog" title="评选优秀作品" width="480px">
      <el-form label-width="80px">
        <el-form-item label="点评语">
          <el-input v-model="note" type="textarea" :rows="3" placeholder="可选：写下点评语" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="saving" @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="confirmMark">确定</el-button>
      </template>
    </el-dialog>

    <!-- 学伴会话（教师只读，设计 §14.6）：与学生侧组件完全分离，无任何写入口 -->
    <CompanionConversationPanel v-model="companionOpen" :conversation-id="activeConversationId" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import Markdown from '../../components/Markdown.vue'
import StateView from '../../components/StateView.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import CompanionConversationPanel from '../../components/CompanionConversationPanel.vue'
import { useCrudList } from '../../composables/useCrudList'
import { homeworkApi } from '../../api'
import { getUser } from '../../utils/auth'

const route = useRoute()
const router = useRouter()
const assignment = ref(null)
const dialog = ref(false)
const note = ref('')
const target = ref(null)
const saving = ref(false) // 评选优秀提交中（防重复提交）
const unmarkingId = ref(null) // 正在取消优秀的提交 id
// 学伴：该作业下本班学生的会话列表（按 student_id 索引），与提交列表按学生对齐
const companionMap = ref({})
// 学伴会话为**教师专属**读接口（后端挂 require_teacher_only，admin 必 403）。
// 本页对 school_admin / super_admin 同样可达（菜单「任务列表」无角色门控、路由只要求 isTeacher()），
// 故必须按角色决定是否发起该请求 —— 否则管理员每次进页都会看到一条
// 「无权限访问该资源」的红字弹窗（缺陷 D-403-1）。
const canViewCompanion = getUser()?.role === 'teacher'
const companionOpen = ref(false)
const activeConversationId = ref(null)

// 作业提交审阅：单个作业的「作业详情 + 全部提交」一次取回。useCrudList 会把
// page / page_size 传进 wrapper（P1-3 分页），透传给后端列表接口即可。
// 学伴会话列表为附加信息：拉取失败时降级为空（学伴列为空），且非教师角色不发起该请求
// （接口为教师专属），不阻断提交列表展示。
const { items, page, pageSize, total, loading, error, load } = useCrudList(async (params) => {
  const [a, s] = await Promise.all([
    homeworkApi.assignment(route.params.id),
    homeworkApi.submissions(route.params.id, {
      page: params.page,
      page_size: params.page_size,
    }),
  ])
  assignment.value = a
  await loadCompanions()
  return { items: s.items, total: s.total }
})

/** 拉取本作业的学伴会话列表（教师只读，设计 §14.2），失败降级为空对象 */
async function loadCompanions() {
  // 非教师角色（school_admin / super_admin）无该接口权限，直接跳过，避免必然的 403 弹窗
  if (!canViewCompanion) return
  try {
    const res = await homeworkApi.companionConversations(
      route.params.id,
      { page: 1, page_size: 200 },
      { _silent: true }
    )
    const map = {}
    for (const c of res?.items || []) {
      map[c.student_id] = c
    }
    companionMap.value = map
  } catch (e) {
    companionMap.value = {}
  }
}

/** 提交行 ⇒ 对应学生的学伴会话（无则返回 null） */
function companionOf(row) {
  return companionMap.value[row.student_id] || null
}

function openCompanion(conv) {
  if (!conv?.conversation_id) return
  activeConversationId.value = conv.conversation_id
  companionOpen.value = true
}

onMounted(load)

function mark(row) {
  target.value = row
  note.value = ''
  dialog.value = true
}

function openDetail(row) {
  router.push(`/admin/homework/${route.params.id}/submissions/${row.id}`)
}

async function confirmMark() {
  // 防重复提交：确定按钮无 loading 时双击会并发两个 POST，第二个请求的「已入选」预检
  // 先于第一个请求的写入生效，最终撞数据库唯一索引报 409「数据冲突」。
  if (saving.value) return
  saving.value = true
  try {
    await homeworkApi.markExcellent(target.value.id, { note: note.value })
    ElMessage.success('已评选为优秀作品')
    dialog.value = false
    load()
  } catch (e) {
    // 失败原因由全局拦截器提示（如「该作品已入选优秀」）
  } finally {
    saving.value = false
  }
}

async function unmark(row) {
  if (unmarkingId.value === row.id) return
  unmarkingId.value = row.id
  try {
    await homeworkApi.unmarkExcellent(row.id)
    ElMessage.success('已取消优秀')
    await load()
  } catch (e) {
    // 失败原因由全局拦截器提示
  } finally {
    unmarkingId.value = null
  }
}

// AI 批改：单份触发（已有成功结果则重跑覆盖）；未批改 / 失败的提交也可单独补批
const aiGradingId = ref(null)

/** 单份批改按钮文案：正在批改中 / 已批改可重跑 / 尚未批改 */
function aiGradeText(status) {
  if (status === 'pending') return '批改中'
  return status === 'success' ? '重新批改' : 'AI 批改'
}

async function aiGrade(row) {
  // 兜底：状态尚未刷新时按钮可能未禁用，此处再挡一次（后端也会幂等空操作）
  if (row.ai_grading_status === 'pending') {
    ElMessage.info('该提交正在批改中，请稍候')
    return
  }
  // 已成功的提交重跑会再次消耗一次 AI 额度：先二次确认，取消则直接返回
  if (row.ai_grading_status === 'success') {
    try {
      await ElMessageBox.confirm(
        '该份已批改，重新批改会再次消耗一次 AI 额度，确认继续？',
        '确认重新批改',
        { type: 'warning' }
      )
    } catch (e) {
      return // 用户取消
    }
  }
  aiGradingId.value = row.id
  try {
    const res = await homeworkApi.aiGradeSubmission(row.id)
    // 后端对「已在批改中」返回 200 + queued=0，这是信息而非错误
    if (res && res.queued === 0 && res.reason) {
      ElMessage.info(res.reason)
    } else {
      ElMessage.success('已发起 AI 批改，稍后刷新查看结果')
    }
    // 批改在后台线程执行，稍作延迟再拉取，避免立刻刷新仍是「批改中」
    setTimeout(load, 1200)
  } catch (e) {
    // 失败原因（总开关未开启 / 未配凭证 / 额度耗尽）由全局拦截器提示
  } finally {
    aiGradingId.value = null
  }
}
</script>

<style scoped>
.content-preview {
  max-height: 120px;
  overflow: hidden;
  position: relative;
  -webkit-line-clamp: 5;
  display: -webkit-box;
  -webkit-box-orient: vertical;
}
.content-preview :deep(.md-body) {
  font-size: 13px;
}
.content-preview :deep(.md-body) h1,
.content-preview :deep(.md-body) h2,
.content-preview :deep(.md-body) h3 {
  font-size: 14px;
  margin: 4px 0;
}
.content-preview :deep(.md-body) p {
  margin: 4px 0;
}
.content-preview :deep(.md-body) pre {
  margin: 4px 0;
  padding: 6px 10px;
  font-size: 12px;
}
.content-preview :deep(.md-body) img {
  max-width: 200px;
  max-height: 150px;
}
.empty {
  text-align: center;
  color: #9ca3af;
  padding: 40px 0;
}
.muted {
  color: #9ca3af;
  font-size: 13px;
}
</style>
