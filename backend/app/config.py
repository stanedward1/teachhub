"""应用配置中心：基于 pydantic-settings 统一从环境变量 / backend/.env 读取。

设计要点：
- 保留全部既有属性名与默认值（全局存在大量 ``settings.XXX`` 引用）。
- ``.env`` 使用绝对路径加载，避免受当前工作目录影响。
- ``CORS_ORIGINS`` 兼容「逗号分隔字符串」与「列表」两种形态。
- 生产环境强制校验 ``SECRET_KEY``（弱密钥 / 短密钥直接启动失败）。
"""
import os
from typing import Annotated

from dotenv import load_dotenv
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# 兼容既有语义：把 .env 注入 os.environ，供其他仍使用 os.getenv 的模块（如 database.py）读取
load_dotenv()

# 仅供本地开发兜底，生产环境禁止使用
_DEV_SECRET_KEY = "teachhub-dev-secret-key"

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

# backend/.env 绝对路径
_ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")


def _split_csv(value):
    """把「逗号分隔字符串」或序列统一成去空白后的字符串列表（供各列表型配置复用）。"""
    if value is None:
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return value


class Settings(BaseSettings):
    """全局配置项。"""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    APP_NAME: str = "TeachHub"
    APP_VERSION: str = "1.0.0"
    ENV: str = "development"  # development / production

    # 未配置时开发环境用兜底值；生产环境在下方强制校验
    SECRET_KEY: str = _DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    # 刷新令牌有效期（天）。F3：access token 过期后用它静默换取新的令牌对（轮换）。
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # 数据库连接串：默认 MySQL（生产/开发统一），切换只需改此环境变量
    #   MySQL:      mysql+pymysql://user:pass@localhost:3306/teachhub?charset=utf8mb4
    #   SQLite:     sqlite:///./teachhub.db
    #   PostgreSQL: postgresql://user:pass@localhost:5432/teachhub
    DATABASE_URL: str = "mysql+pymysql://root:root@127.0.0.1:3306/teachhub?charset=utf8mb4"
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    # 头像存储目录：统一派生自 UPLOAD_DIR，避免「avatars」在三处硬编码。
    # 注意：这是磁盘路径，与前端访问的 URL 前缀「/uploads/avatars/」无关。
    AVATAR_DIR: str = os.path.join(UPLOAD_DIR, "avatars")

    # 上传约束
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 默认 20MB
    ALLOWED_UPLOAD_EXTS: set[str] = ALLOWED_UPLOAD_EXTS

    # ---------------- AI 批改（docs/AI-GRADING-PRD.md） ----------------
    # 凭证加密主密钥（可选）。留空则由 SECRET_KEY 派生（开箱即用）；
    # 生产环境建议显式设置，以便日后轮换登录签名密钥时不牵连已存凭证的加解密。
    AI_CREDENTIAL_KEY: str = ""
    # 单次模型调用超时（秒）。批改在后台线程执行，不占用学生提交响应。
    AI_REQUEST_TIMEOUT: int = 60
    # 每日调用次数上限（成本护栏）。总开关是平台级的，限额是唯一的成本刹车。
    AI_DEFAULT_DAILY_LIMIT: int = 200
    # 单次调用 max_tokens 上限（控制单次成本与超长输出）
    AI_DEFAULT_MAX_TOKENS: int = 1200
    # 送入模型的输入字符上限（作业要求 + 正文 + 附件合并后截断）
    AI_MAX_INPUT_CHARS: int = 8000
    # 单个附件抽取出的文本字符上限
    AI_MAX_ATTACHMENT_CHARS: int = 6000

    # CORS：默认放行本地开发端口，生产通过环境变量收敛（逗号分隔或 JSON 列表）
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # 是否信任反向代理传来的 `X-Forwarded-For`（用于按**真实客户端 IP** 限流）。
    # ⚠️ 默认 False。该头可被客户端伪造：只有部署在**自己可控的**反向代理之后、
    # 且代理会重写该头时才可开启，否则攻击者可伪造 IP 绕过 / 干扰限流计数。
    TRUST_PROXY_HEADERS: bool = False

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def _fill_default_secret_key(cls, value):
        """空串 / None 回落到开发兜底值（保持与旧 ``os.getenv(...) or 兜底`` 一致）。"""
        if value is None:
            return _DEV_SECRET_KEY
        if isinstance(value, str) and not value.strip():
            return _DEV_SECRET_KEY
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_list_setting(cls, value):
        """兼容逗号分隔字符串（默认形态），也兼容已是 list/tuple/set 的情况。"""
        return _split_csv(value)

    @model_validator(mode="after")
    def _enforce_production_secret(self):
        """生产环境安全校验：必须显式设置强随机 SECRET_KEY，否则启动失败。"""
        if self.ENV == "production":
            raw = self.SECRET_KEY or ""
            if not raw or raw == _DEV_SECRET_KEY:
                raise RuntimeError(
                    "生产环境必须通过环境变量设置强随机的 SECRET_KEY，且不得使用开发默认值。"
                )
            if len(raw) < 32:
                raise RuntimeError("生产环境 SECRET_KEY 长度不足 32 位，请使用强随机密钥。")
        return self


settings = Settings()
