import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue(),
  ],
  // 依赖预构建：把 CJS 依赖（dayjs 等）提前转 ESM，避免浏览器报
  // "does not provide an export named 'default'" 白屏错误；
  // 全量预构建 element-plus，避免 dev 模式运行时反复发现新依赖触发 reload 卡顿
  optimizeDeps: {
    include: [
      'vue',
      'vue-router',
      'axios',
      'echarts',
      'echarts/core',
      'echarts/charts',
      'echarts/components',
      'echarts/renderers',
      'marked',
      'dompurify',
      'dayjs',
      'lodash-unified',
      'element-plus',
      '@element-plus/icons-vue',
      'vant',
    ],
  },
  server: {
    port: 5173,
    proxy: {
      // ⚠️ `xfwd: true` 必须保留：
      // vite 代理是**对着客户端的那一层**，客户端 IP 只有它知道（`$remote_addr` 等价物）。
      // 不开这个开关时，代理从 localhost 连后端且不带任何转发头 —— 后端只能看到 127.0.0.1，
      // 表现为「学生管理处所有用户的最后登录 IP 都是 127.0.0.1」，且后端无法自行还原
      // （真实 IP 从未到达后端）。开启后 http-proxy 会附加
      // `X-Forwarded-For / X-Forwarded-Proto / X-Forwarded-Host / X-Forwarded-Port`。
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        xfwd: true
      },
      '/uploads': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        xfwd: true
      }
    }
  },
  build: {
    // 代码分割：将第三方库单独打包，利用浏览器缓存
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-vue': ['vue', 'vue-router'],
          'vendor-echarts': ['echarts'],
          'vendor-markdown': ['marked', 'dompurify'],
        }
      }
    },
    // 启用 CSS 代码分割
    cssCodeSplit: true,
    // 资源内联阈值（小于 4KB 的资源内联为 base64）
    assetsInlineLimit: 4096,
  }
})
