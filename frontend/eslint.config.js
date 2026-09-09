import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import prettier from 'eslint-config-prettier'

export default [
  // 忽略构建产物与依赖
  {
    ignores: ['dist/**', 'node_modules/**', 'dist-*/**', '*.d.ts'],
  },
  // 基础 JS 规则（全项目）
  js.configs.recommended,
  // Vue 3 推荐规则（含模板校验）
  ...pluginVue.configs['flat/recommended'],
  // 关闭与 Prettier 冲突的格式规则（必须放最后）
  prettier,
  {
    files: ['**/*.{js,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        // 浏览器全局
        window: 'readonly',
        document: 'readonly',
        localStorage: 'readonly',
        navigator: 'readonly',
        console: 'readonly',
        fetch: 'readonly',
        FormData: 'readonly',
        Blob: 'readonly',
        File: 'readonly',
        URL: 'readonly',
        URLSearchParams: 'readonly',
        AbortController: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
      },
    },
    rules: {
      // Vue 风格：模板多属性换行、组件名多词等（保持宽松，避免大面积报错）
      'vue/multi-word-component-names': 'off',
      'vue/no-v-html': 'off',
      'vue/require-default-prop': 'off',
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-self-closing': 'off',
      'vue/attributes-order': 'off',
      // 历史代码存在大量 try/catch 但忽略错误的写法（catch (e) {}），
      // 渐进接入阶段先放行，后续再逐步清理为有意义的错误处理。
      'no-empty': ['error', { allowEmptyCatch: true }],
      'no-unused-vars': ['warn', { argsIgnorePattern: '^_', caughtErrors: 'none' }],
      'no-console': 'off',
      'no-debugger': 'warn',
    },
  },
]
