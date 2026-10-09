import request from '../../api/request'

// 移动端专用接口（/api/mobile/*）
export const mobileApi = {
  // 学生速查列表（精简字段，默认排除退学）
  students: (params) => request.get('/api/mobile/students', { params }),
  // 学生画像概览
  overview: (id) => request.get(`/api/mobile/students/${id}/overview`),
}
