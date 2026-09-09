#!/usr/bin/env bash
# ============================================================
# TeachHub 一键启动脚本（本地开发 / 服务器部署通用）
#
# 用法:
#   bash start.sh                 # 启动（缺依赖会自动安装），默认 SQLite
#   DB_ENGINE=mysql bash start.sh # 使用 MySQL（需先填写下方连接信息）
#   bash start.sh --install-only  # 只装依赖，不启动服务
#
# 数据库默认 SQLite（零配置，与项目/Docker 默认一致）。
# 生产环境建议改用 `docker compose up -d`（见 README）。
# ============================================================

# 必须用 bash 运行（脚本使用了 bash 数组等特性）
if [ -z "${BASH_VERSION:-}" ]; then
  echo "[ERROR] 请用 bash 运行本脚本：bash start.sh"
  exit 1
fi

set -euo pipefail

# ---------- 颜色输出 ----------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------- 路径配置 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
ENV_FILE="$BACKEND_DIR/.env"

# ---------- 数据库配置 ----------
# 默认 SQLite（零配置）。切换 MySQL：export DB_ENGINE=mysql 后运行，
# 并确认下方账号/密码与服务器实际一致。
DB_ENGINE="${DB_ENGINE:-sqlite}"   # sqlite | mysql
DB_USER="root"
DB_PASSWORD="password"
DB_NAME="teachhub"
DB_HOST="127.0.0.1"
DB_PORT="3306"

# ---------- 架构检测 ----------
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64)  ARCH_LABEL="x86_64" ;;
  aarch64|arm64) ARCH_LABEL="arm64" ;;
  *)             ARCH_LABEL="$ARCH" ;;
esac
info "检测到 CPU 架构: $ARCH_LABEL"
info "数据库引擎: $DB_ENGINE"

# ---------- 依赖检查：系统包 ----------
check_system_deps() {
  info "检查系统依赖..."
  local missing=()

  # Python 3
  if ! command -v python3 >/dev/null 2>&1; then missing+=(python3); fi

  # MariaDB/MySQL 服务端（仅 MySQL 模式需要）
  if [ "$DB_ENGINE" = "mysql" ]; then
    if ! systemctl is-active --quiet mariadb 2>/dev/null && \
       ! systemctl is-active --quiet mysql 2>/dev/null && \
       ! command -v mysqld >/dev/null 2>&1 && \
       ! command -v mariadbd >/dev/null 2>&1; then
      missing+=(mariadb-server)
    fi
  fi

  # Node.js 由 check_nodejs 单独处理（需用 nodesource 装高版本，apt 默认源版本过低）

  if [ ${#missing[@]} -gt 0 ]; then
    warn "缺少系统包: ${missing[*]}，尝试安装（需要 root/sudo 权限）..."
    if command -v apt-get >/dev/null 2>&1; then
      sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
        "${missing[@]}" python3-venv python3-pip curl
    elif command -v yum >/dev/null 2>&1; then
      sudo yum install -y "${missing[@]}" python3-venv python3-pip nodejs npm
    elif command -v dnf >/dev/null 2>&1; then
      sudo dnf install -y "${missing[@]}" python3-venv python3-pip nodejs npm
    else
      error "不支持的包管理器，请手动安装: ${missing[*]}"
      exit 1
    fi
  fi
  info "系统依赖 OK"
}

# ---------- Node.js 检查/安装（前端需要 18+，用 nodesource 装 20 LTS） ----------
check_nodejs() {
  local need_install=false
  local node_major=0

  # 检测 node + npm 是否都存在，且主版本 >= 18
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    need_install=true
  else
    node_major="$(node -v 2>/dev/null | sed 's/^v//' | cut -d. -f1)"
    if ! [[ "$node_major" =~ ^[0-9]+$ ]] || [ "$node_major" -lt 18 ]; then
      need_install=true
    fi
  fi

  if [ "$need_install" = true ]; then
    warn "Node.js 缺失或版本过低（需要 18+），尝试安装 Node 20 LTS（需要 sudo 权限）..."
    if command -v apt-get >/dev/null 2>&1; then
      # Debian/Ubuntu
      sudo apt-get update -y
      sudo apt-get install -y curl ca-certificates
      curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
      sudo apt-get install -y nodejs
    elif command -v dnf >/dev/null 2>&1; then
      # Fedora / RHEL 8+
      curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
      sudo dnf install -y nodejs
    elif command -v yum >/dev/null 2>&1; then
      # CentOS / RHEL 7
      curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
      sudo yum install -y nodejs
    else
      error "无法自动安装 Node.js，请手动安装 Node 18+ 后重试"
      exit 1
    fi
  fi

  # 最终校验
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    error "Node.js 安装失败，请手动安装 Node 18+ 后重试"
    exit 1
  fi
  info "Node.js $(node -v) / npm $(npm -v) OK"
}

# ---------- 数据库初始化（仅 MySQL 模式） ----------
setup_database() {
  if [ "$DB_ENGINE" != "mysql" ]; then
    info "使用 SQLite，跳过数据库服务检查"
    return 0
  fi

  info "检查 MariaDB/MySQL 服务..."
  if ! systemctl is-active --quiet mariadb 2>/dev/null && \
     ! systemctl is-active --quiet mysql 2>/dev/null; then
    sudo systemctl start mariadb 2>/dev/null || sudo systemctl start mysql 2>/dev/null || true
    sleep 2
  fi

  info "初始化数据库 ${DB_NAME} ..."
  # 优先尝试 unix_socket 认证的 root（Debian/Ubuntu 默认）
  if sudo mysql -e "SELECT 1" >/dev/null 2>&1; then
    sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '${DB_PASSWORD}'; FLUSH PRIVILEGES;" 2>/dev/null || true
    sudo mysql -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  elif mysql -u"$DB_USER" -p"$DB_PASSWORD" -h"$DB_HOST" -P"$DB_PORT" -e "SELECT 1" >/dev/null 2>&1; then
    mysql -u"$DB_USER" -p"$DB_PASSWORD" -h"$DB_HOST" -P"$DB_PORT" \
      -e "CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  else
    error "无法连接数据库。请确认："
    error "  1. MariaDB/MySQL 已安装并启动"
    error "  2. 脚本顶部的 DB_USER / DB_PASSWORD 与实际一致（当前: ${DB_USER}/${DB_PASSWORD}）"
    error "  或改用 SQLite：DB_ENGINE=sqlite bash start.sh"
    exit 1
  fi
  info "数据库 ${DB_NAME} 就绪"
}

# ---------- 后端依赖安装 ----------
setup_backend() {
  info "配置后端虚拟环境..."
  cd "$BACKEND_DIR"

  # 创建 venv（若不存在或损坏）
  if [ ! -x ".venv/bin/python" ]; then
    rm -rf .venv
    python3 -m venv .venv
  fi

  # 安装依赖（阿里云镜像，国内友好）
  info "安装后端依赖（阿里云镜像）..."
  .venv/bin/pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ -q
  .venv/bin/pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ -q

  # 确定 DATABASE_URL
  if [ "$DB_ENGINE" = "mysql" ]; then
    DATABASE_URL_VALUE="mysql+pymysql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?charset=utf8mb4"
  else
    DATABASE_URL_VALUE="sqlite:///./teachhub.db"
  fi

  # 生成 .env（不存在时）；已存在则尊重用户已有配置
  if [ ! -f "$ENV_FILE" ]; then
    warn "未找到 .env，基于当前配置生成..."
    cat > "$ENV_FILE" <<EOF
# 运行环境：development / production
ENV=development

# 数据库连接串
DATABASE_URL=${DATABASE_URL_VALUE}

# JWT 签名密钥
SECRET_KEY=teachhub-dev-secret-key-2026
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS 允许来源（逗号分隔）
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://0.0.0.0:5173

# 文件上传上限（字节，默认 20MB）
MAX_UPLOAD_SIZE=20971520
EOF
    info ".env 已生成"
  else
    DATABASE_URL_VALUE="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '[:space:]')"
    info "使用已有 .env 配置（DATABASE_URL=$DATABASE_URL_VALUE）"
  fi
  export DATABASE_URL="$DATABASE_URL_VALUE"

  info "后端依赖 OK"
}

# ---------- 数据库迁移 + 首次 seed ----------
migrate_and_seed() {
  cd "$BACKEND_DIR"
  info "执行数据库迁移 (alembic upgrade head)..."
  if ! .venv/bin/python -m alembic upgrade head; then
    error "数据库迁移失败，无法连接数据库。请检查: $DATABASE_URL"
    error "  - SQLite：确认 backend/ 目录可写"
    error "  - MySQL：确认服务已启动、账号密码正确"
    exit 1
  fi

  info "检查演示数据..."
  .venv/bin/python - <<'PYEOF'
from app.database import SessionLocal
from app.models import User

db = SessionLocal()
try:
    if db.query(User).count() == 0:
        from app.seed import seed_all
        seed_all()
        print("[seed] 已初始化演示数据（admin/admin123, teacher/123456 等）")
    else:
        print("[seed] 数据库已有数据，跳过初始化")
finally:
    db.close()
PYEOF
}

# ---------- esbuild 原生二进制完整性检查 ----------
# 背景：npm 从镜像源（npmmirror 等）安装时，optionalDependencies 的原生
# 二进制可能未正确下载（@esbuild/linux-arm64 只有 JS 包装、缺 ELF 二进制），
# 导致 vite/esbuild 卡死无输出。此函数检测并自动修复。
check_esbuild_binary() {
  cd "$FRONTEND_DIR"

  local esbuild_pkg=""
  case "$ARCH_LABEL" in
    x86_64) esbuild_pkg="@esbuild/linux-x64" ;;
    arm64)  esbuild_pkg="@esbuild/linux-arm64" ;;
    *)      info "非主流架构，跳过 esbuild 原生二进制检查"; return 0 ;;
  esac

  local pkg_dir="node_modules/$esbuild_pkg"
  local bin_path="$pkg_dir/bin/esbuild"

  local binary_ok=false
  if [ -f "$bin_path" ]; then
    local magic
    magic="$(head -c 4 "$bin_path" 2>/dev/null | od -An -tx1 | tr -d ' \n')"
    if [ "$magic" = "7f454c46" ]; then
      binary_ok=true
    fi
  fi

  if [ "$binary_ok" = true ]; then
    info "esbuild 原生二进制 OK ($esbuild_pkg)"
    return 0
  fi

  warn "esbuild 原生二进制缺失/损坏（$esbuild_pkg），尝试自动修复..."
  local esbuild_version
  esbuild_version="$(node -e "console.log(require('esbuild/package.json').version)" 2>/dev/null || echo "0.21.5")"
  info "检测到 esbuild 版本: $esbuild_version"

  local tmp_dir
  tmp_dir="$(mktemp -d)"
  local tgz_path="$tmp_dir/pkg.tgz"

  if command -v npm >/dev/null 2>&1; then
    (cd "$tmp_dir" && npm pack "$esbuild_pkg@$esbuild_version" \
      --registry=https://registry.npmjs.org >/dev/null 2>&1 && \
      tar -xzf ./*.tgz) || {
      error "下载 $esbuild_pkg@$esbuild_version 失败，请手动运行:"
      error "  cd $FRONTEND_DIR && npm rebuild esbuild --registry=https://registry.npmjs.org"
      rm -rf "$tmp_dir"
      return 1
    }
  else
    error "npm 不可用，无法修复 esbuild"
    rm -rf "$tmp_dir"
    return 1
  fi

  if [ -f "$tmp_dir/package/bin/esbuild" ]; then
    mkdir -p "$pkg_dir/bin"
    cp "$tmp_dir/package/bin/esbuild" "$bin_path"
    chmod 755 "$bin_path"
    local magic2
    magic2="$(head -c 4 "$bin_path" | od -An -tx1 | tr -d ' \n')"
    if [ "$magic2" = "7f454c46" ]; then
      info "esbuild 原生二进制修复成功: $bin_path ($(stat -c%s "$bin_path") bytes)"
      rm -rf "$tmp_dir"
      return 0
    else
      error "修复后仍非 ELF 二进制，请手动检查"
      rm -rf "$tmp_dir"
      return 1
    fi
  fi

  error "下载包中未找到二进制，修复失败"
  rm -rf "$tmp_dir"
  return 1
}

# ---------- 前端依赖安装 ----------
setup_frontend() {
  info "配置前端依赖..."
  cd "$FRONTEND_DIR"

  if [ ! -d "node_modules" ] || [ ! -x "node_modules/.bin/vite" ]; then
    warn "node_modules 缺失或不完整，重新安装..."
    rm -rf node_modules package-lock.json
    npm install --registry=https://registry.npmmirror.com
  fi

  check_esbuild_binary
  info "前端依赖 OK"
}

# ---------- 启动服务 ----------
start_services() {
  # 清理旧进程（按进程名 + 端口多管齐下，避免端口被残留进程占用导致换端口/绑定失败）
  pkill -f "uvicorn" 2>/dev/null || true
  pkill -f "run.py" 2>/dev/null || true
  pkill -f "vite" 2>/dev/null || true
  pkill -f "npm run dev" 2>/dev/null || true
  if command -v fuser >/dev/null 2>&1; then
    fuser -k 8080/tcp 2>/dev/null || true
    fuser -k 5173/tcp 2>/dev/null || true
  fi
  sleep 2

  info "启动后端 (uvicorn :8080)..."
  cd "$BACKEND_DIR"
  nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 > /tmp/teachhub_backend.log 2>&1 &
  echo "  后端日志: /tmp/teachhub_backend.log"

  info "启动前端 (vite :5173)..."
  cd "$FRONTEND_DIR"
  nohup npm run dev -- --host 0.0.0.0 > /tmp/teachhub_frontend.log 2>&1 &
  echo "  前端日志: /tmp/teachhub_frontend.log"

  # 等待端口就绪
  info "等待服务启动..."
  local ok=0
  for ((i=0; i<30; i++)); do
    if curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1 && \
       curl -sf -o /dev/null http://127.0.0.1:5173/ >/dev/null 2>&1; then
      ok=1
      break
    fi
    sleep 1
  done

  echo ""
  echo "======================================================"
  if [ "$ok" = "1" ]; then
    echo "  TeachHub 启动完成!"
    echo "  前端:  http://localhost:5173/   (局域网: http://<本机IP>:5173/)"
    echo "  后端:  http://localhost:8080/   (API 文档: /docs)"
    echo "  数据库: $DB_ENGINE ($DATABASE_URL)"
    echo ""
    echo "  登录账号（seed 数据）："
    echo "    管理员 admin / admin123"
    echo "    教师   teacher / 123456"
    echo "    学生   班级+姓名 / 123456"
  else
    echo "  服务可能未就绪，请查看日志排查："
    echo "    后端: tail -50 /tmp/teachhub_backend.log"
    echo "    前端: tail -50 /tmp/teachhub_frontend.log"
  fi
  echo "======================================================"
  echo ""
}

# ---------- 主流程 ----------
main() {
  check_system_deps
  check_nodejs
  setup_database
  setup_backend
  migrate_and_seed
  setup_frontend

  if [ "${1:-}" = "--install-only" ]; then
    info "依赖安装完成（--install-only），未启动服务"
    exit 0
  fi

  start_services
}

main "$@"
