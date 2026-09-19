/**
 * 浏览器端文件下载工具。
 *
 * 抽取自 Students.vue / Scores.vue / Exams.vue 中重复出现的
 * 「Blob → createObjectURL → a.click() → revokeObjectURL」样板（原共 5 处），
 * 统一 Excel 导出与导入模板下载的行为。
 *
 * 注意：request.js 的响应拦截器返回的是 `response.data`，
 * 因此这里收到的 `data` 已经是解包后的 Blob（而非 axios 响应对象）。
 */

const EXCEL_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/**
 * 把后端返回的二进制内容保存为本地文件。
 *
 * @param {Blob|ArrayBuffer|string} data 响应体（通常为 Blob）
 * @param {string} filename 下载文件名，需含扩展名，如 `学生花名册.xlsx`
 */
export function downloadExcel(data, filename) {
  const blob = new Blob([data], { type: EXCEL_MIME })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export { EXCEL_MIME }
