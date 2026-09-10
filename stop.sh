#!/usr/bin/env bash
# ============================================================
# TeachHub 一键停止脚本（本地开发 / 服务器部署通用）
#
# 用法:
#   bash stop.sh          # 停止后端(8080) + 前端(5173) 所有相关进程
#   bash stop.sh backend  # 只停止后端
#   bash stop.sh frontend # 只停止前端
#
# 说明: 与 start.sh 启动的进程特征对应，按「进程名 + 端口」
#       多管齐下清理，避免残留进程占用端口导致下次启动绑定失败。
# ============================================================

set -uo pipefail

# ---------- 颜色输出 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------- 目标选择 ----------
TARGET="${1:-all}"
case "$TARGET" in
  all)      STOP_BACKEND=1; STOP_FRONTEND=1 ;;
  backend)  STOP_BACKEND=1; STOP_FRONTEND=0 ;;
  frontend) STOP_BACKEND=0; STOP_FRONTEND=1 ;;
  *)
    error "未知参数: $TARGET（可选: all | backend | frontend）"
    exit 1
    ;;
esac

# ---------- 平台检测 ----------
IS_WINDOWS=0
if command -v pkill >/dev/null 2>&1; then
  HAS_PKILL=1
else
  HAS_PKILL=0
fi
if command -v fuser >/dev/null 2>&1; then
  HAS_FUSER=1
else
  HAS_FUSER=0
fi
# Windows（Git Bash/MSYS）下用 taskkill + netstat 兜底
if command -v taskkill >/dev/null 2>&1 && command -v netstat >/dev/null 2>&1 && [ "$HAS_PKILL" = "0" ]; then
  IS_WINDOWS=1
fi

# 按端口取 PID 并终止（Linux 用 fuser，Windows 用 netstat+taskkill）
kill_port() {
  local port="$1"
  if [ "$IS_WINDOWS" = "1" ]; then
    local pids
    pids="$(netstat -ano 2>/dev/null | grep ":$port " | grep LISTENING | awk '{print $NF}' | sort -u)"
    if [ -n "$pids" ]; then
      for pid in $pids; do
        taskkill /F /PID "$pid" >/dev/null 2>&1 && info "  已终止 PID $pid (端口 $port)" || true
      done
    fi
  elif [ "$HAS_FUSER" = "1" ]; then
    fuser -k "$port/tcp" 2>/dev/null && info "  已释放 $port 端口" || true
  fi
}

# ---------- 停止后端 ----------
stop_backend() {
  info "停止后端 (uvicorn :8080) ..."

  if [ "$HAS_PKILL" = "1" ]; then
    pkill -f "uvicorn" 2>/dev/null && info "  已停止 uvicorn 进程" || true
    pkill -f "run.py" 2>/dev/null && info "  已停止 run.py 进程" || true
  fi

  # 按端口清理（兜底，确保 8080 释放）
  kill_port 8080
}

# ---------- 停止前端 ----------
stop_frontend() {
  info "停止前端 (vite :5173) ..."

  if [ "$HAS_PKILL" = "1" ]; then
    pkill -f "vite" 2>/dev/null && info "  已停止 vite 进程" || true
    pkill -f "npm run dev" 2>/dev/null && info "  已停止 npm run dev 进程" || true
  fi

  kill_port 5173
}

# 检查端口是否仍被占用
port_in_use() {
  local port="$1"
  if [ "$IS_WINDOWS" = "1" ]; then
    netstat -ano 2>/dev/null | grep ":$port " | grep LISTENING | grep -q .
  elif [ "$HAS_FUSER" = "1" ]; then
    fuser "$port/tcp" >/dev/null 2>&1
  else
    # 无 fuser 时用 ss/lsof 兜底探测
    (command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ":$port ") || \
    (command -v lsof >/dev/null 2>&1 && lsof -iTCP:$port -sTCP:LISTEN 2>/dev/null | grep -q .) || return 1
  fi
}

# ---------- 主流程 ----------
main() {
  echo "======================================================"
  echo "  TeachHub 停止脚本 (target: $TARGET)"
  echo "======================================================"

  [ "$STOP_BACKEND"  = "1" ] && stop_backend
  [ "$STOP_FRONTEND" = "1" ] && stop_frontend

  # 等待端口释放
  sleep 2

  echo ""
  echo "======================================================"
  if [ "$STOP_BACKEND" = "1" ]; then
    if port_in_use 8080; then
      warn "后端 8080 端口可能仍被占用，请手动排查"
    else
      info "后端已停止 (8080 端口已释放)"
    fi
  fi
  if [ "$STOP_FRONTEND" = "1" ]; then
    if port_in_use 5173; then
      warn "前端 5173 端口可能仍被占用，请手动排查"
    else
      info "前端已停止 (5173 端口已释放)"
    fi
  fi
  echo "======================================================"
  echo ""
}

main "$@"
