<template>
  <el-upload
    v-if="!row.is_dropped_out"
    :show-file-list="false"
    :before-upload="beforeAvatarUpload"
    :http-request="(opt) => handleStudentAvatar(opt, row)"
    accept=".jpg,.jpeg,.png,.gif,.webp"
  >
    <el-avatar
      :size="32"
      :src="row.avatar"
      style="
        cursor: pointer;
        background: linear-gradient(135deg, #2563eb, #4f46e5);
        color: #fff;
        font-weight: 600;
        font-size: 13px;
      "
    >
      {{ row.name?.[0] }}
    </el-avatar>
  </el-upload>
  <el-avatar
    v-else
    :size="32"
    :src="row.avatar"
    style="
      background: linear-gradient(135deg, #9ca3af, #6b7280);
      color: #fff;
      font-weight: 600;
      font-size: 13px;
    "
  >
    {{ row.name?.[0] }}
  </el-avatar>
</template>

<script setup>
/**
 * 学生头像上传单元格。
 *
 * 从 Students.vue 表格「头像」列原样搬出：包含上传前的格式/大小校验、
 * 自定义 http-request 上传，以及头像圆角与配色。上传成功后通过 `updated`
 * 事件把新头像 url 回传给父组件（父组件负责写回行数据）。
 */
import { ElMessage } from 'element-plus'
import { studentApi } from '../../../api'

defineProps({
  /** 表格当前行学生对象 */
  row: { type: Object, required: true },
})

const emit = defineEmits(['updated'])

/** 上传前校验：仅允许 JPG/PNG/GIF/WebP，且不超过 2MB。 */
function beforeAvatarUpload(file) {
  const allowed = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  if (!allowed.includes(file.type)) {
    ElMessage.error('仅支持 JPG/PNG/GIF/WebP 格式')
    return false
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.error('头像不能超过 2MB')
    return false
  }
  return true
}

/** 自定义上传：把文件提交给学生头像接口，成功后回传新头像 url。 */
async function handleStudentAvatar(options, row) {
  try {
    const fd = new FormData()
    fd.append('file', options.file)
    const res = await studentApi.uploadAvatar(row.id, fd)
    emit('updated', res.avatar)
    ElMessage.success('头像更新成功')
  } catch (e) {}
}
</script>
