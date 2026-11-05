#!/usr/bin/env node
/**
 * TeachHub 前端生产服务（默认 :5173）
 *
 * 部署形态：前端 :5173 提供 `dist` 构建产物，后端 :8080 只提供 API。
 * 浏览器看到的仍是单一来源（`/api` 由本进程反向代理），所以不存在跨域问题。
 *
 * 为什么不用 `npm run dev`：
 *   Vite dev 按模块原样下发、不做压缩、每个模块都带 `Cache-Control: no-cache`，
 *   实测首屏 23 个请求 / 4.5MB —— 公网访问就是「页面很久加载不出来」。
 *
 * 为什么不用 `vite preview`：
 *   它面向本地验收，使用 sirv 且未开启 gzip（sirv 只有磁盘上存在同名 `.gz`
 *   文件时才走压缩），而 `npm run build` 不产出 `.gz`。本文件用 node 内置模块
 *   实现 gzip + 长缓存 + SPA 回落 + API 反向代理，零第三方依赖，行为与后端
 *   托管（`SERVE_FRONTEND=1`）保持一致。
 *
 * 用法：
 *   cd frontend && npm run build && npm run serve
 *
 * 环境变量：
 *   PORT=5173                        前端端口
 *   HOST=0.0.0.0                     监听地址
 *   API_ORIGIN=http://127.0.0.1:8080 后端地址
 *   DIST_DIR=dist                    产物目录（相对 frontend/）
 */
import http from 'node:http'
import path from 'node:path'
import zlib from 'node:zlib'
import { createReadStream, promises as fsp } from 'node:fs'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const DIST = path.resolve(__dirname, process.env.DIST_DIR || 'dist')
const PORT = Number(process.env.PORT || 5173)
const HOST = process.env.HOST || '0.0.0.0'
const API_ORIGIN = new URL(process.env.API_ORIGIN || 'http://127.0.0.1:8080')

/** 这些前缀不属于前端路由，原样转发给后端（/docs 等是 FastAPI 自带页面）。 */
const PROXY_PREFIXES = [
  '/api',
  '/uploads',
  '/health',
  '/metrics',
  '/docs',
  '/redoc',
  '/openapi.json',
]

/** 小于该体积不压缩：省下的字节抵不上 CPU 与头部开销。 */
const MIN_GZIP_BYTES = 1024

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.avif': 'image/avif',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.otf': 'font/otf',
  '.txt': 'text/plain; charset=utf-8',
  '.webmanifest': 'application/manifest+json',
}

/** 只压缩文本类资源；图片/字体本身已压缩，再 gzip 只浪费 CPU。 */
const COMPRESSIBLE =
  /^(?:text\/|application\/(?:javascript|json|xml|manifest\+json)|image\/svg\+xml)/

/** 构建产物带内容哈希 ⇒ 可永久缓存；其余（index.html 等）每次校验。 */
const CACHE_IMMUTABLE = 'public, max-age=31536000, immutable'
const CACHE_REVALIDATE = 'no-cache'

/** gzip 结果按 (路径 + mtime + 大小) 缓存：同一份构建只压一次。 */
const gzipCache = new Map()
const GZIP_CACHE_LIMIT = 256

function etagOf(stat) {
  return `W/"${stat.size.toString(16)}-${Math.floor(stat.mtimeMs).toString(16)}"`
}

async function statOrNull(p) {
  try {
    const s = await fsp.stat(p)
    return s
  } catch {
    return null
  }
}

/** 解析成 dist 内的真实路径；越界（../、绝对路径）返回 null。 */
function resolveInside(urlPath) {
  const rel = urlPath.replace(/^\/+/, '')
  const abs = path.resolve(DIST, rel)
  if (abs !== DIST && !abs.startsWith(DIST + path.sep)) return null
  return abs
}

async function sendFile(req, res, filePath, stat, cacheControl) {
  const type = MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream'
  const etag = etagOf(stat)

  res.setHeader('ETag', etag)
  res.setHeader('Cache-Control', cacheControl)
  res.setHeader('X-Content-Type-Options', 'nosniff')

  if (req.headers['if-none-match'] === etag) {
    res.statusCode = 304
    res.end()
    return
  }

  const compressible = COMPRESSIBLE.test(type) && stat.size >= MIN_GZIP_BYTES
  // Vary 必须无条件发送：同一 URL 会按 Accept-Encoding 返回不同实体。
  if (compressible) res.setHeader('Vary', 'Accept-Encoding')

  const useGzip = compressible && /\bgzip\b/.test(String(req.headers['accept-encoding'] || ''))
  let body = null
  if (useGzip) {
    const tag = `${stat.size}-${Math.floor(stat.mtimeMs).toString(36)}`
    const hit = gzipCache.get(filePath)
    if (hit && hit.tag === tag) {
      body = hit.body
    } else {
      body = zlib.gzipSync(await fsp.readFile(filePath), { level: 6 })
      if (gzipCache.size >= GZIP_CACHE_LIMIT) gzipCache.clear()
      gzipCache.set(filePath, { tag, body })
    }
    res.setHeader('Content-Encoding', 'gzip')
  }

  res.setHeader('Content-Type', type)
  res.setHeader('Content-Length', body ? body.length : stat.size)

  if (req.method === 'HEAD') {
    res.end()
    return
  }
  if (body) {
    res.end(body)
    return
  }

  await new Promise((resolve, reject) => {
    const stream = createReadStream(filePath)
    stream.on('error', reject)
    stream.on('end', resolve)
    stream.pipe(res)
  })
}

function proxyToApi(req, res) {
  const upstream = http.request(
    {
      hostname: API_ORIGIN.hostname,
      port: API_ORIGIN.port || 80,
      method: req.method,
      path: req.url,
      headers: { ...req.headers, host: API_ORIGIN.host },
    },
    (upRes) => {
      res.writeHead(upRes.statusCode || 502, upRes.headers)
      upRes.pipe(res)
    }
  )

  upstream.on('error', (err) => {
    const body = JSON.stringify({
      detail: `后端不可达 ${API_ORIGIN.origin}：${err.code || err.message}`,
    })
    if (!res.headersSent) {
      res.writeHead(502, {
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Length': Buffer.byteLength(body),
      })
    }
    res.end(body)
  })

  // 上传大文件也走这里：req 直接 pipe 给上游，不落内存
  req.pipe(upstream)
}

async function handleStatic(req, res, urlPath) {
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.writeHead(405, { Allow: 'GET, HEAD' })
    res.end()
    return
  }

  let filePath = resolveInside(urlPath)
  if (!filePath) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' })
    res.end('Forbidden')
    return
  }

  let stat = await statOrNull(filePath)
  if (stat && stat.isDirectory()) {
    filePath = path.join(filePath, 'index.html')
    stat = await statOrNull(filePath)
  }

  if (stat && stat.isFile()) {
    const isHashedAsset = urlPath.startsWith('/assets/')
    await sendFile(req, res, filePath, stat, isHashedAsset ? CACHE_IMMUTABLE : CACHE_REVALIDATE)
    return
  }

  // SPA 回落：只有「看起来是前端路由」的请求才回 index.html。
  // 带扩展名的（/favicon.ico、/x.png）如实 404，否则会返回 HTML 造成误导。
  const looksLikeRoute = !path.extname(urlPath)
  if (looksLikeRoute && String(req.headers.accept || '').includes('text/html')) {
    const indexPath = path.join(DIST, 'index.html')
    const indexStat = await statOrNull(indexPath)
    if (indexStat) {
      await sendFile(req, res, indexPath, indexStat, CACHE_REVALIDATE)
      return
    }
  }

  res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
  res.end(`404 Not Found: ${urlPath}`)
}

const server = http.createServer((req, res) => {
  let urlPath
  try {
    urlPath = decodeURIComponent(new URL(req.url || '/', 'http://localhost').pathname)
  } catch {
    res.writeHead(400, { 'Content-Type': 'text/plain; charset=utf-8' })
    res.end('Bad Request')
    return
  }

  if (PROXY_PREFIXES.some((p) => urlPath === p || urlPath.startsWith(`${p}/`))) {
    proxyToApi(req, res)
    return
  }

  handleStatic(req, res, urlPath).catch((err) => {
    console.error('[serve] 处理失败', urlPath, err)
    if (!res.headersSent) {
      res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' })
    }
    res.end('Internal Server Error')
  })
})

async function main() {
  const indexStat = await statOrNull(path.join(DIST, 'index.html'))
  if (!indexStat) {
    console.error(`[serve] 未找到构建产物：${DIST}`)
    console.error('[serve] 请先执行：cd frontend && npm run build')
    process.exit(1)
  }

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.error(`[serve] 端口 ${PORT} 已被占用，换端口：PORT=5174 npm run serve`)
    } else {
      console.error('[serve] 服务错误', err)
    }
    process.exit(1)
  })

  server.listen(PORT, HOST, () => {
    console.log(`[serve] TeachHub 前端已启动  http://${HOST}:${PORT}`)
    console.log(`[serve] 产物目录 ${DIST}`)
    console.log(`[serve] API 反向代理 → ${API_ORIGIN.origin}（/api /uploads /docs …）`)
  })
}

function shutdown(signal) {
  console.log(`\n[serve] 收到 ${signal}，正在关闭…`)
  server.close(() => process.exit(0))
  // 有长连接时兜底退出
  setTimeout(() => process.exit(0), 3000).unref()
}
process.on('SIGINT', () => shutdown('SIGINT'))
process.on('SIGTERM', () => shutdown('SIGTERM'))

main().catch((err) => {
  console.error('[serve] 启动失败', err)
  process.exit(1)
})
