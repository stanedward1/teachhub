<template>
  <div class="schools-page">
    <!-- 概览 -->
    <div class="stat-cards">
      <div class="stat-card">
        <div class="stat-num">{{ overview.school_count ?? '-' }}</div>
        <div class="stat-label">学校总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ overview.active_school_count ?? '-' }}</div>
        <div class="stat-label">启用中</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ overview.student_count ?? '-' }}</div>
        <div class="stat-label">学生总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ overview.teacher_count ?? '-' }}</div>
        <div class="stat-label">教师总数</div>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <el-button type="primary" @click="openCreate">开通学校</el-button>
    </div>

    <!-- 列表 -->
    <StateView
      :loading="loading"
      :error="error"
      :empty="!items.length"
      :columns="8"
      empty-description="暂无学校"
      @retry="load"
    >
      <el-table :data="items" v-loading="loading" border>
        <el-table-column prop="name" label="学校名称" min-width="180" />
        <el-table-column prop="code" label="代码" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="class_count" label="班级" width="80" align="center" />
        <el-table-column prop="student_count" label="学生" width="80" align="center" />
        <el-table-column prop="teacher_count" label="教师" width="80" align="center" />
        <el-table-column prop="phone" label="电话" min-width="140" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              :type="row.status === 'active' ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 'active' ? '停用' : '启用' }}
            </el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="primary" plain @click="openAiSettings(row)">
              AI 配置
            </el-button>
            <el-button size="small" type="danger" @click="removeSchool(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </StateView>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialog" :title="isEdit ? '编辑学校' : '开通学校'" width="520px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="学校名称" required>
          <el-input v-model="form.name" placeholder="如：XX 职业技术学校" />
        </el-form-item>
        <el-form-item label="学校代码" required>
          <el-input v-model="form.code" placeholder="如：XYZJ01" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.address" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <template v-if="!isEdit">
          <el-divider content-position="left">首位学校管理员（可选）</el-divider>
          <el-form-item label="管理员账号">
            <el-input v-model="form.admin_username" placeholder="如：admin02" />
          </el-form-item>
          <el-form-item label="管理员姓名">
            <el-input v-model="form.admin_name" />
          </el-form-item>
          <el-form-item label="初始密码">
            <el-input v-model="form.admin_password" placeholder="默认 School@123" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveSchool">保存</el-button>
      </template>
    </el-dialog>

    <!-- AI 配置对话框（超管专用，docs/DESIGN-AI校级能力.md §3 D5 / §7） -->
    <el-dialog v-model="aiDialogVisible" :title="`AI 配置 — ${aiSchool?.name || ''}`" width="680px">
      <div v-loading="aiLoading">
        <!-- AI 批改 -->
        <div class="ai-section-label">AI 批改</div>
        <el-form label-width="210px">
          <el-form-item label="批改开关">
            <el-radio-group v-model="aiForm.grading_enabled" :disabled="aiLoading || aiSaving">
              <el-radio value="follow">跟随平台</el-radio>
              <el-radio value="on">开启</el-radio>
              <el-radio value="off">关闭</el-radio>
            </el-radio-group>
            <div class="ai-hint">
              平台当前：{{
                aiPlatform.grading_enabled ? '开启' : '关闭'
              }}（平台级，前往「平台设置」修改）。 「跟随平台」= 不单独设置，随平台总闸变化。
            </div>
          </el-form-item>
          <el-form-item label="每日调用次数上限（额度池）">
            <el-radio-group v-model="aiForm.grading_limit_mode" :disabled="aiLoading || aiSaving">
              <el-radio value="follow">不限（跟随默认）</el-radio>
              <el-radio value="custom">自定义</el-radio>
            </el-radio-group>
            <el-input-number
              v-if="aiForm.grading_limit_mode === 'custom'"
              v-model="aiForm.grading_daily_limit"
              :min="0"
              :max="1000000"
              :disabled="aiLoading || aiSaving"
              style="margin-left: 12px"
            />
            <div class="ai-hint">
              平台池当前：{{ aiPlatform.grading_daily_limit }} 次/日；本校今日已用
              {{ aiUsage.grading?.used ?? 0 }} 次（校级生效上限：{{
                aiUsage.grading?.school_limit ?? '不限'
              }}）。 0 表示今日完全停用；「不限」= 不设校级额度池，仅受平台池约束。
            </div>
          </el-form-item>
        </el-form>

        <!-- AI 学伴 -->
        <div class="ai-section-label ai-section-gap">AI 学伴</div>
        <el-form label-width="210px">
          <el-form-item label="学伴开关">
            <el-radio-group v-model="aiForm.companion_enabled" :disabled="aiLoading || aiSaving">
              <el-radio value="follow">跟随平台</el-radio>
              <el-radio value="on">开启</el-radio>
              <el-radio value="off">关闭</el-radio>
            </el-radio-group>
            <div class="ai-hint">
              平台当前：{{
                aiPlatform.companion_enabled ? '开启' : '关闭'
              }}（平台级，前往「平台设置」修改）。 「跟随平台」= 不单独设置，随平台总闸变化。
            </div>
          </el-form-item>
          <el-form-item label="每日调用次数上限（额度池）">
            <el-radio-group v-model="aiForm.companion_limit_mode" :disabled="aiLoading || aiSaving">
              <el-radio value="follow">不限（跟随默认）</el-radio>
              <el-radio value="custom">自定义</el-radio>
            </el-radio-group>
            <el-input-number
              v-if="aiForm.companion_limit_mode === 'custom'"
              v-model="aiForm.companion_daily_limit"
              :min="0"
              :max="1000000"
              :disabled="aiLoading || aiSaving"
              style="margin-left: 12px"
            />
            <div class="ai-hint">
              平台池当前：{{ aiPlatform.companion_daily_limit }} 次/日；本校今日已用
              {{ aiUsage.companion?.used ?? 0 }} 次（校级生效上限：{{
                aiUsage.companion?.school_limit ?? '不限'
              }}）。 0 表示今日完全停用；「不限」= 不设校级额度池，仅受平台池约束。
            </div>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="aiDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="aiSaving" @click="saveAiSettings">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import StateView from '../../components/StateView.vue'
import { useCrudList } from '../../composables/useCrudList'
import { schoolApi, adminApi } from '../../api'

const saving = ref(false)
// 启用/停用学校的状态锁：防双击造成重复切换（写入在途时忽略重复触发）
const togglingStatus = ref(false)
const overview = ref({})
const dialog = ref(false)
const isEdit = ref(false)
const editId = ref(null)

const emptyForm = () => ({
  name: '',
  code: '',
  address: '',
  phone: '',
  admin_username: '',
  admin_name: '',
  admin_password: '',
})
const form = reactive(emptyForm())

// 学校全量列表 + 平台概览两路请求合并取回；全量不分页（paginated:false），保持原行为等价。
const { items, loading, error, load } = useCrudList(
  async (params) => {
    const [s, o] = await Promise.all([schoolApi.list(params), adminApi.platformOverview()])
    overview.value = o
    return { items: s.items || [], total: (s.items || []).length }
  },
  { paginated: false }
)

function openCreate() {
  isEdit.value = false
  editId.value = null
  Object.assign(form, emptyForm())
  dialog.value = true
}

function openEdit(row) {
  isEdit.value = true
  editId.value = row.id
  Object.assign(form, {
    name: row.name,
    code: row.code,
    address: row.address,
    phone: row.phone,
    admin_username: '',
    admin_name: '',
    admin_password: '',
  })
  dialog.value = true
}

async function saveSchool() {
  if (!form.name || !form.code) return ElMessage.warning('请填写学校名称和代码')
  saving.value = true
  try {
    if (isEdit.value) {
      await schoolApi.update(editId.value, {
        name: form.name,
        address: form.address,
        phone: form.phone,
      })
      ElMessage.success('已保存')
    } else {
      await schoolApi.create(form)
      ElMessage.success('学校已开通')
    }
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function toggleStatus(row) {
  if (togglingStatus.value) return // 防双击：写入在途时忽略重复触发
  togglingStatus.value = true
  try {
    const next = row.status === 'active' ? 'disabled' : 'active'
    await schoolApi.setStatus(row.id, next)
    ElMessage.success(next === 'active' ? '已启用' : '已停用')
    load()
  } finally {
    togglingStatus.value = false
  }
}

async function removeSchool(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除学校「${row.name}」吗？该校若有班级数据将无法删除。`,
      '删除确认',
      { type: 'warning' }
    )
  } catch {
    return // 用户取消确认框：静默返回，不弹任何提示
  }
  await schoolApi.remove(row.id)
  ElMessage.success('已删除')
  load()
}

// ---------------- 校级 AI 能力配置（超管专用，docs/DESIGN-AI校级能力.md §3 D5 / §7） ----------------
const aiDialogVisible = ref(false)
const aiLoading = ref(false)
const aiSaving = ref(false)
const aiSchool = ref(null)
const aiPlatform = ref({
  grading_enabled: false,
  grading_daily_limit: 200,
  companion_enabled: false,
  companion_daily_limit: 6000,
})
const aiUsage = ref({
  grading: { used: 0, school_limit: null },
  companion: { used: 0, school_limit: null },
})

// 三态表单：开关 'follow'（跟随平台）| 'on' | 'off'；额度池 'follow'（不限）| 'custom'
const aiForm = reactive({
  grading_enabled: 'follow',
  grading_limit_mode: 'follow',
  grading_daily_limit: 0,
  companion_enabled: 'follow',
  companion_limit_mode: 'follow',
  companion_daily_limit: 0,
})

// GET/PUT 同构响应 → 回填表单。override 是原始字符串（"1"/"0"/数字串/null）：
// null = 无覆盖（跟随平台 / 不限），"1" = 开，"0" = 关，数字串 = 自定义上限
function applyAiResponse(res) {
  if (res.platform) aiPlatform.value = res.platform
  if (res.usage_today) aiUsage.value = res.usage_today
  const ov = res.school_override || {}
  aiForm.grading_enabled =
    ov.grading_enabled == null ? 'follow' : String(ov.grading_enabled) === '1' ? 'on' : 'off'
  aiForm.companion_enabled =
    ov.companion_enabled == null ? 'follow' : String(ov.companion_enabled) === '1' ? 'on' : 'off'
  for (const kind of ['grading', 'companion']) {
    const raw = ov[`${kind}_daily_limit`]
    if (raw == null) {
      aiForm[`${kind}_limit_mode`] = 'follow'
      aiForm[`${kind}_daily_limit`] = 0
    } else {
      aiForm[`${kind}_limit_mode`] = 'custom'
      aiForm[`${kind}_daily_limit`] = Number(raw) || 0
    }
  }
}

// 组装 PUT body：弹窗总是四字段全发；「跟随平台 / 不限」发显式 null（后端语义 =
// 清除覆盖恢复默认），开关发 true/false，自定义池发非负整数。
function buildAiPayload() {
  return {
    grading_enabled: aiForm.grading_enabled === 'follow' ? null : aiForm.grading_enabled === 'on',
    grading_daily_limit:
      aiForm.grading_limit_mode === 'follow'
        ? null
        : Math.trunc(Number(aiForm.grading_daily_limit) || 0),
    companion_enabled:
      aiForm.companion_enabled === 'follow' ? null : aiForm.companion_enabled === 'on',
    companion_daily_limit:
      aiForm.companion_limit_mode === 'follow'
        ? null
        : Math.trunc(Number(aiForm.companion_daily_limit) || 0),
  }
}

async function openAiSettings(row) {
  aiSchool.value = { id: row.id, name: row.name }
  aiDialogVisible.value = true
  aiLoading.value = true
  try {
    applyAiResponse(await adminApi.schoolAiSettings(row.id))
  } catch (e) {
    // 错误提示由 request.js 拦截器统一弹出；回填失败时关闭弹窗避免展示空白表单
    aiDialogVisible.value = false
    console.error('[Schools] 加载校级 AI 配置失败:', e)
  } finally {
    aiLoading.value = false
  }
}

async function saveAiSettings() {
  for (const kind of ['grading', 'companion']) {
    if (aiForm[`${kind}_limit_mode`] !== 'custom') continue
    const v = aiForm[`${kind}_daily_limit`]
    if (v == null || Number.isNaN(Number(v)) || v < 0) {
      return ElMessage.warning('请填写自定义上限（0 表示今日完全停用）')
    }
  }
  aiSaving.value = true
  try {
    // PUT 响应与 GET 同构，直接回填刷新弹窗，免二次请求
    applyAiResponse(await adminApi.setSchoolAiSettings(aiSchool.value.id, buildAiPayload()))
    ElMessage.success('已保存')
  } catch (e) {
    console.error('[Schools] 保存校级 AI 配置失败:', e)
  } finally {
    aiSaving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.stat-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.stat-card {
  background: #fff;
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 20px;
}
.stat-num {
  font-size: 30px;
  font-weight: 600;
  color: var(--el-color-primary);
}
.stat-label {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.toolbar {
  margin-bottom: 16px;
}
.ai-section-label {
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  margin: 0 0 12px;
}
.ai-section-gap {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f3f4f6;
}
.ai-hint {
  font-size: 12px;
  color: #9ca3af;
  line-height: 1.6;
  margin-top: 6px;
  width: 100%;
}
</style>
