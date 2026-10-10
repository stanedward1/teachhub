import { onBeforeUnmount } from 'vue'
import * as echarts from 'echarts/core'

/**
 * ECharts 实例生命周期薄封装：收敛各图表组件重复的
 * 「重建式 init（旧实例先 dispose）、dispose、组件卸载自动清理」样板。
 *
 * 刻意保持薄，不统一各文件的语义差异：
 * - option 构建与 setOption 时机仍由各组件自己控制（本封装不碰 option）
 * - init() 沿用原样板「重建」语义：先 dispose 旧实例再 init（顺带避免
 *   「There is a chart instance already initialized on the dom」告警）
 * - 卸载清理默认挂 onBeforeUnmount；原本就没有卸载清理语义的调用方
 *   （如 ScoreAnalysis 的趋势弹窗）传 { disposeOnUnmount: false } 保持原样
 */
export function useEChart(elRef, { disposeOnUnmount = true } = {}) {
  let chart = null

  /**
   * 在 elRef 当前挂载的容器上重建实例并返回；调用方需自行保证容器已挂载
   * （与原样板的守卫条件一致，由各组件在 init 前自行 return）。
   */
  function init() {
    if (chart) chart.dispose()
    chart = echarts.init(elRef.value)
    return chart
  }

  /** 销毁当前实例（若有）并置空引用。 */
  function dispose() {
    if (chart) {
      chart.dispose()
      chart = null
    }
  }

  if (disposeOnUnmount) {
    onBeforeUnmount(dispose)
  }

  return { init, dispose, get: () => chart }
}
