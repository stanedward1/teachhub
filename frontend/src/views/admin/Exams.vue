<template>
  <div>
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索试卷标题"
        clearable
        style="width: 220px"
        @keyup.enter="load"
        @clear="load"
      />
      <el-button @click="load">查询</el-button>
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openUpload">上传试卷</el-button>
    </div>

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="6"
        empty-description="暂无试卷"
        @retry="load"
      >
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="title" label="试卷名称" min-width="180" />
          <el-table-column label="文件类型" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="fileTagType(row.filetype)">
                {{ row.filetype || '—' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="exam_type" label="试卷分类" width="120">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ row.exam_type || '单元测验' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="文件大小" width="110">
            <template #default="{ row }">
              {{ formatSize(row.filesize) }}
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="上传时间" width="170" />
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.filepath" link type="primary" @click="downloadFile(row)"
                >下载</el-button
              >
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </StateView>
    </div>

    <!-- 上传试卷弹窗 -->
    <el-dialog v-model="uploadDialog" title="上传试卷" width="520px" @close="resetUpload">
      <el-form label-width="80px">
        <el-form-item label="试卷名称" required>
          <el-input v-model="uploadForm.title" placeholder="请输入试卷名称" />
        </el-form-item>
        <el-form-item label="试卷分类">
          <el-select v-model="uploadForm.exam_type" style="width: 100%">
            <el-option label="单元测验" value="单元测验" />
            <el-option label="期中测试" value="期中测试" />
            <el-option label="期末考试" value="期末考试" />
            <el-option label="随堂练习" value="随堂练习" />
            <el-option label="模拟考试" value="模拟考试" />
          </el-select>
        </el-form-item>
        <el-form-item label="试卷文件" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            :before-upload="() => false"
            accept=".pdf,.doc,.docx"
            drag
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">将文件拖到此处，或<em>点击选择</em></div>
            <template #tip>
              <div class="upload-tip">支持 .pdf / .doc / .docx 格式，最大 20MB</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="doUpload">
          {{ uploading ? '上传中...' : '开始上传' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑试卷弹窗 -->
    <el-dialog v-model="editDialog" title="编辑试卷" width="440px">
      <el-form label-width="80px">
        <el-form-item label="试卷名称" required>
          <el-input v-model="editForm.title" />
        </el-form-item>
        <el-form-item label="试卷分类">
          <el-select v-model="editForm.exam_type" style="width: 100%">
            <el-option label="单元测验" value="单元测验" />
            <el-option label="期中测试" value="期中测试" />
            <el-option label="期末考试" value="期末考试" />
            <el-option label="随堂练习" value="随堂练习" />
            <el-option label="模拟考试" value="模拟考试" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useDebouncedRef } from '../../composables/useDebouncedRef'
import { ElMessage, ElMessageBox } from 'element-plus'
import SortBar from '../../components/SortBar.vue'
import StateView from '../../components/StateView.vue'
import { useSort } from '../../composables/useSort'
import { examApi } from '../../api'

const rawItems = ref([])
const { order, useSorted } = useSort('exams')
const items = useSorted(rawItems)
const keyword = useDebouncedRef('', 300)
watch(keyword, () => load())
const loading = ref(false)
const error = ref(false)

// 上传
const uploadDialog = ref(false)
const uploadRef = ref(null)
const uploading = ref(false)
const uploadForm = reactive({ title: '', exam_type: '单元测验' })
const selectedFile = ref(null)

// 编辑
const editDialog = ref(false)
const saving = ref(false)
const editForm = reactive({ title: '', exam_type: '' })
const editingId = ref(null)

onMounted(load)

async function load() {
  loading.value = true
  error.value = false
  try {
    const res = await examApi.list({ keyword: keyword.value })
    rawItems.value = res.items
  } catch (e) {
    error.value = true
  } finally {
    loading.value = false
  }
}

function fileTagType(ext) {
  const map = { '.pdf': 'danger', '.doc': 'primary', '.docx': 'primary' }
  return map[ext] || 'info'
}

function formatSize(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// 上传
function openUpload() {
  resetUpload()
  uploadDialog.value = true
}

function resetUpload() {
  uploadForm.title = ''
  uploadForm.exam_type = '单元测验'
  selectedFile.value = null
  uploadRef.value?.clearFiles()
}

function onFileChange(file) {
  selectedFile.value = file.raw
  if (!uploadForm.title) {
    uploadForm.title = file.name.replace(/\.[^.]+$/, '')
  }
}

function onFileRemove() {
  selectedFile.value = null
}

async function doUpload() {
  if (!uploadForm.title.trim()) return ElMessage.warning('请输入试卷名称')
  if (!selectedFile.value) return ElMessage.warning('请选择试卷文件')
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('title', uploadForm.title.trim())
    fd.append('exam_type', uploadForm.exam_type)
    fd.append('file', selectedFile.value)
    await examApi.upload(fd)
    ElMessage.success('上传成功')
    uploadDialog.value = false
    load()
  } catch (e) {
  } finally {
    uploading.value = false
  }
}

// 下载
async function downloadFile(row) {
  try {
    const blob = await examApi.download(row.id)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = row.filename || row.title
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载失败')
  }
}

// 编辑
function openEdit(row) {
  editingId.value = row.id
  editForm.title = row.title
  editForm.exam_type = row.exam_type || '单元测验'
  editDialog.value = true
}

async function saveEdit() {
  if (!editForm.title.trim()) return ElMessage.warning('请输入试卷名称')
  saving.value = true
  try {
    await examApi.update(editingId.value, {
      title: editForm.title.trim(),
      exam_type: editForm.exam_type,
    })
    ElMessage.success('保存成功')
    editDialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除试卷「${row.title}」吗？`, '提示', { type: 'warning' })
  await examApi.remove(row.id)
  ElMessage.success('删除成功')
  load()
}
</script>

<style scoped>
.upload-icon {
  font-size: 48px;
  color: var(--brand-light);
}
.upload-text {
  color: var(--text-secondary);
  font-size: 14px;
  margin-top: 8px;
}
.upload-text em {
  color: var(--brand);
  font-style: normal;
}
.upload-tip {
  color: var(--text-tertiary);
  font-size: 12px;
  margin-top: 4px;
}
</style>
