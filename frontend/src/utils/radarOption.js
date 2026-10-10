/**
 * 四维雷达图 option 共享 builder。
 *
 * StudentCard.vue 与 StudentProfile.vue 两处雷达 option 为逐字重复的样板：
 * radar.center/radius/indicator、系列线色/点色 #2563eb、symbol: 'circle'
 * 完全相同（写死在此）；仅 tooltip、axisName 配色、系列 symbolSize、
 * 数据项 areaColor 与数据名存在实测差异，由参数表达。产出 option 与
 * 原字面量 JSON.stringify 逐字节相等（含键序）。
 *
 * 注意：mobile StudentOverview.vue 的雷达 option 结构不同（无 center/axisName、
 * lineStyle/itemStyle 内联在 data 项中），无法用参数干净表达，保留原样。
 *
 * 纯数据组装函数、不涉及 Vue 响应式与生命周期，按项目惯例放 utils
 * （composables/ 只放依赖 Vue 上下文的 use* 组合式函数）。
 */

/**
 * @param {Object} opts
 * @param {number[]} opts.value     四维数值 [学业, 品德, 出勤, 技能]
 * @param {string} opts.dataName    系列数据项名称
 * @param {string} opts.areaColor   数据项 areaStyle 填充色
 * @param {number} opts.symbolSize  系列标记大小
 * @param {Object} opts.axisName    radar.axisName 样式
 * @param {Object} [opts.tooltip]   tooltip 配置，默认 {}
 */
export function buildRadarOption({
  value,
  dataName,
  areaColor,
  symbolSize,
  axisName,
  tooltip = {},
}) {
  return {
    tooltip,
    radar: {
      center: ['50%', '50%'],
      radius: '65%',
      indicator: [
        { name: '学业', max: 100 },
        { name: '品德', max: 100 },
        { name: '出勤', max: 100 },
        { name: '技能', max: 100 },
      ],
      axisName,
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value,
            name: dataName,
            areaStyle: { color: areaColor },
          },
        ],
        lineStyle: { color: '#2563eb', width: 2 },
        itemStyle: { color: '#2563eb' },
        symbol: 'circle',
        symbolSize,
      },
    ],
  }
}
