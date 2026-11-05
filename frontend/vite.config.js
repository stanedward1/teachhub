import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver, VantResolver } from 'unplugin-vue-components/resolvers'

export default defineConfig({
  plugins: [
    vue(),
    // 第三方组件按需引入（模板里写 <el-xxx> / <van-xxx> 时自动 import 对应模块）：
    // - Element Plus：组件 + **样式**都按需（importStyle: 'css'），首屏只带登录页
    //   用到的那几个组件的 CSS；函数式组件（ElMessage 等）的样式在 main.js 里补。
    // - Vant：组件随所在页面 chunk 一起懒加载 —— PC 端首屏因此完全不含 Vant
    // dirs: [] 表示不扫描 src/components 自动注册（本地组件一律显式 import，行为不变）
    Components({
      dts: false,
      dirs: [],
      resolvers: [ElementPlusResolver({ importStyle: 'css' }), VantResolver()],
    }),
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
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // 第三方库分组规则。
        //
        // 用**函数式**而不是对象式：对象式 `{ x: ['echarts'] }` 会以该包为入口，
        // 把**整包**强制拉进 chunk —— 代码里用的是 `echarts/core` 只按需注册
        // RadarChart，列进对象式会让按需注册失效（体积从 130KB 涨到 500KB+）。
        // 函数式只对「已进入依赖图」的模块归组，按需仍然有效。
        //
        // element-plus 刻意**不**手动分组：交给 Rollup 按「被哪些页面引用」自动切，
        // 首屏（登录页）就只加载登录页真正用到的组件，而不是后台全部组件。
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          const p = id.replace(/\\/g, '/')
          if (p.includes('/@element-plus/icons-vue/')) return 'vendor-icons'
          if (/\/node_modules\/(@vue|vue|vue-router|pinia|vue-demi)\//.test(p)) return 'vendor-vue'
          if (/\/node_modules\/(marked|dompurify)\//.test(p)) return 'vendor-markdown'
          // 只在 /m 页面被引用 ⇒ 随路由懒加载，不进 PC 首屏
          if (/\/node_modules\/(vant|@vant)\//.test(p)) return 'vendor-vant'
        },
        // 按需引入会把 element-plus 拆成上百个 1~5KB 的小 chunk。HTTP/1.1 下
        // 浏览器只开 6 个并发，请求条数比总体积更影响首屏（每轮都要等 RTT）。
        // 把小于 30KB 的 chunk 并回引用方：按需不变（首屏仍不含没用到的组件），
        // 产物文件数 154 → 110。注：实测 30KB 与 50KB 的请求数相同（剩下的
        // chunk 都大于阈值），故取更保守的 30KB。
        experimentalMinChunkSize: 30 * 1024,
      },
    },
    // 启用 CSS 代码分割
    cssCodeSplit: true,
    // 资源内联阈值（小于 4KB 的资源内联为 base64）
    assetsInlineLimit: 4096,
  },
})
