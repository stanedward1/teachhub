# TeachHub 后端镜像
FROM python:3.11-slim

WORKDIR /app

# 系统依赖（bcrypt 无需额外系统库；此处预留）
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 先装依赖，利用镜像层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码与迁移脚本
COPY . .

# 数据目录（SQLite）与上传目录
RUN mkdir -p /app/data /app/uploads

EXPOSE 8080

CMD ["python", "docker-entrypoint.py"]
