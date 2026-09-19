<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="560px"
    @update:model-value="$emit('update:modelValue', $event)"
    @open="reset"
    @close="reset"
  >
    <el-form label-width="80px">
      <el-form-item label="导入模板">
        <el-button type="primary" link @click="onDownloadTemplate">{{ templateLabel }}</el-button>
        <span style="color: #909399; font-size: 12px; margin-left: 8px">请按模板格式填写数据</span>
      </el-form-item>
      <el-form-item label="选择文件">
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :limit="1"
          :on-change="onFileChange"
          :on-remove="onFileRemove"
          :before-upload="() => false"
          :accept="accept"
          drag
        >
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="upload-text">将 Excel 文件拖到此处，或<em>点击选择</em></div>
          <template #tip>
            <div class="upload-tip">{{ tip }}</div>
          </template>
        </el-upload>
      </el-form-item>
    </el-form>

    <!-- 导入结果 -->
    <div v-if="result" class="import-result">
      <el-alert
        :title="`导入完成：成功 ${result.success} 条，失败 ${result.errors?.length || 0} 条`"
        :type="result.errors?.length ? 'warning' : 'success'"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
      />
      <div v-if="result.errors?.length" class="error-list">
        <div v-for="(err, i) in result.errors" :key="i" class="error-item">{{ err }}</div>
      </div>
    </div>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">关闭</el-button>
      <el-button type="primary" :loading="importing" @click="doImport">
        {{ importing ? '导入中...' : '开始导入' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
/**
 * 通用 Excel 批量导入弹窗。
 *
 * 抽取自 Students.vue 与 Scores.vue 中逐字重复的导入弹窗（约 120 行 ×2），
 * 统一「下载模板 → 拖拽选择文件 → 上传 → 展示成功/失败明细」流程。
 * 业务差异（导入哪个接口、模板文件名）通过 props 注入。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadExcel } from '../composables/useDownload'

const props = defineProps({
  /** 弹窗显隐（v-model） */
  modelValue: { type: Boolean, default: false },
  /** 弹窗标题 */
  title: { type: String, default: '批量导入' },
  /** 模板下载链接文案 */
  templateLabel: { type: String, default: '下载标准模板' },
  /** 文件选择框 accept */
  accept: { type: String, default: '.xlsx,.xls' },
  /** 上传区提示文案 */
  tip: { type: String, default: '仅支持 .xlsx / .xls 格式' },
  /**
   * 导入请求：接收 FormData，返回 `{ success, errors }` 形状的结果。
   * 由父组件注入对应模块的 API，如 `(fd) => studentApi.import(fd)`。
   */
  importFn: { type: Function, required: true },
  /**
   * 模板下载请求（可选）：返回二进制内容；不传则隐藏「下载模板」按钮。
   */
  templateUrl: { type: Function, default: null },
  /** 下载模板时的文件名 */
  templateFilename: { type: String, default: '导入模板.xlsx' },
})

const emit = defineEmits(['update:modelValue', 'success'])

const uploadRef = ref(null)
const importing = ref(false)
const file = ref(null)
const result = ref(null)

function reset() {
  file.value = null
  result.value = null
  uploadRef.value?.clearFiles()
}

function onFileChange(f) {
  file.value = f.raw
  result.value = null
}

function onFileRemove() {
  file.value = null
}

async function onDownloadTemplate() {
  if (!props.templateUrl) return
  const res = await props.templateUrl()
  downloadExcel(res, props.templateFilename)
}

async function doImport() {
  if (!file.value) return ElMessage.warning('请选择文件')
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    const res = await props.importFn(fd)
    result.value = res
    if (res.success > 0) {
      ElMessage.success(`成功导入 ${res.success} 条数据`)
      emit('success', res)
    }
  } catch (e) {
    console.error('[ImportDialog] 导入失败:', e)
  } finally {
    importing.value = false
  }
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
.import-result {
  margin-top: 16px;
}
.error-list {
  max-height: 200px;
  overflow-y: auto;
  background: #fef2f2;
  border-radius: 8px;
  padding: 12px;
}
.error-item {
  font-size: 13px;
  color: #dc2626;
  line-height: 1.8;
  padding: 2px 0;
}
</style>
