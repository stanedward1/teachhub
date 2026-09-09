import os

from dotenv import load_dotenv

load_dotenv()

# 仅供本地开发兜底，生产环境禁止使用
_DEV_SECRET_KEY = "techhub-dev-secret-key"

# 学生积分初始基础分（每个学生默认 100 分，加减分在此基础上累加）
BASE_POINTS = 100

# 允许上传的文件扩展名白名单
ALLOWED_UPLOAD_EXTS = {
    # 图片
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
    # 文档
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # 文本 / 压缩包
    ".txt", ".md", ".zip", ".rar", ".7z",
    # 代码 / 作业
    ".c", ".cpp", ".py", ".java", ".js", ".ts", ".html", ".css",
}


class Settings:
    APP_NAME: str = "TechHub"
    APP_VERSION: str = "1.0.0"
    ENV: str = os.getenv("ENV", "development")  # development / production

    # 未配置时开发环境用兜底值；生产环境在下方强制校验
    SECRET_KEY: str = os.getenv("SECRET_KEY", "") or _DEV_SECRET_KEY
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
    )
    # 数据库连接串：默认 SQLite（单文件零配置），切换只需改此环境变量
    #   MySQL:      mysql+pymysql://user:pass@localhost:3306/techhub?charset=utf8mb4
    #   PostgreSQL: postgresql://user:pass@localhost:5432/techhub
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./techhub.db")
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

    # 上传约束
    MAX_UPLOAD_SIZE: int = int(
        os.getenv("MAX_UPLOAD_SIZE", str(20 * 1024 * 1024))  # 默认 20MB
    )
    ALLOWED_UPLOAD_EXTS: set = ALLOWED_UPLOAD_EXTS

    # CORS：默认放行本地开发端口，生产通过环境变量收敛
    CORS_ORIGINS: list = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if o.strip()
    ]


settings = Settings()

# 生产环境安全校验：必须显式设置强随机 SECRET_KEY
if settings.ENV == "production":
    raw = os.getenv("SECRET_KEY", "")
    if not raw or raw == _DEV_SECRET_KEY:
        raise RuntimeError(
            "生产环境必须通过环境变量设置强随机的 SECRET_KEY，且不得使用开发默认值。"
        )
    if len(raw) < 32:
        raise RuntimeError("生产环境 SECRET_KEY 长度不足 32 位，请使用强随机密钥。")
