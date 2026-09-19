<template>
  <div>
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索资源名称"
        clearable
        style="width: 220px"
        @keyup.enter="reload"
        @clear="reload"
      />
      <el-button @click="reload">查询</el-button>
      <SortBar v-model="order" />
      <div class="spacer"></div>
      <el-button type="primary" @click="openCreate">上传资源</el-button>
    </div>

    <div class="page-card">
      <StateView
        :loading="loading"
        :error="error"
        :empty="!items.length"
        :columns="5"
        empty-description="暂无资源"
        @retry="load"
      >
        <el-table :data="items" v-loading="loading" style="width: 100%">
          <el-table-column prop="name" label="资源名称" min-width="220" />
          <el-table-column prop="category" label="分类" width="120">
            <template #default="{ row }"
              ><el-tag size="small" type="info">{{ row.category }}</el-tag></template
            >
          </el-table-column>
          <el-table-column prop="filename" label="文件名" min-width="180" />
          <el-table-column prop="created_at" label="上传时间" width="170" />
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.filepath" link type="primary" @click="download(row)"
                >下载</el-button
              >
              <el-button link type="danger" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </StateView>
    </div>

    <el-dialog v-model="dialog" title="上传资源" width="460px">
      <el-form label-width="80px">
        <el-form-item label="名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" style="width: 100%">
            <el-option
              v-for="c in ['课件', '教案', '习题', '素材', '其他']"
              :key="c"
              :label="c"
              :value="c"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <el-upload :show-file-list="false" :http-request="doUpload" :limit="1">
            <el-button>选择文件</el-button>
          </el-upload>
          <span v-if="form.filename" style="margin-left: 10px; font-size: 13px; color: #6b7280">{{
            form.filename
          }}</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { useDebouncedRef } from '../../composables/useDebouncedRef'
import { ElMessage } from 'element-plus'
import SortBar from '../../components/SortBar.vue'
import StateView from '../../components/StateView.vue'
import { useSort } from '../../composables/useSort'
import { useCrudList } from '../../composables/useCrudList'
import { resourceApi, uploadFile } from '../../api'

const { order, useSorted } = useSort('resources')
const keyword = useDebouncedRef('', 300)
const dialog = ref(false)
const saving = ref(false)
const form = reactive({ name: '', category: '课件', filename: '', filepath: '' })
const {
  items: rawItems,
  loading,
  error,
  load,
  reload,
  remove,
} = useCrudList(resourceApi.list, {
  removeApi: resourceApi.remove,
  buildParams: () => ({ keyword: keyword.value }),
  removeTip: (row) => `确定删除资源「${row.name}」吗？`,
})
const items = useSorted(rawItems)
watch(keyword, reload)

onMounted(load)

function openCreate() {
  Object.assign(form, { name: '', category: '课件', filename: '', filepath: '' })
  dialog.value = true
}

async function doUpload({ file }) {
  const res = await uploadFile(file)
  form.filepath = res.filepath
  form.filename = res.filename
  if (!form.name) form.name = res.filename
}

async function save() {
  if (!form.name) return ElMessage.warning('请填写资源名称')
  saving.value = true
  try {
    await resourceApi.create(form)
    ElMessage.success('保存成功')
    dialog.value = false
    load()
  } catch (e) {
  } finally {
    saving.value = false
  }
}

function download(row) {
  window.open('/uploads/' + row.filepath, '_blank')
}
</script>
