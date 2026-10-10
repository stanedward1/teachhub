/**
 * 本地日期格式化为 YYYY-MM-DD。
 * 不用 toISOString()：其走 UTC，清晨（UTC 与本地跨天时）会返回差一天的日期。
 */
export function formatDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
