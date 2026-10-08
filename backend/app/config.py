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
    # 单次调用 max_tokens 上限（控制单次成本与超长输出）。
    # 推理模型（如 deepseek-flash）的思考 token 与正文 content 共用同一 max_tokens 预算，
    # 思考会挤占正文空间；批改已默认关闭思考（见 AI_THINKING_MODE），此处 2048 给正文留足余量。
    AI_DEFAULT_MAX_TOKENS: int = 2048
    # 思考模式开关：下发到请求体 ``thinking.type``；``disabled`` 关闭思考
    # （批改是有界抽取类任务，不需要长思考，且思考会挤占正文预算）。
    # 空串 = 不发送该字段，交由服务商默认行为。
    AI_THINKING_MODE: str = "disabled"
    # 思考强度：下发 ``reasoning_effort``（low/high/max）；空串 = 不发送，交由服务商默认。
    AI_REASONING_EFFORT: str = ""
    # 截断重试时单次 max_tokens 的上限，防止重试把成本放大到不可控。
    AI_MAX_TOKENS_CEILING: int = 8192
    # 送入模型的输入字符上限（作业要求 + 正文 + 附件合并后截断）
    AI_MAX_INPUT_CHARS: int = 8000
    # 单个附件抽取出的文本字符上限
    AI_MAX_ATTACHMENT_CHARS: int = 6000
    # 单张图片送入多模态的字节上限。base64 后体积约 ×1.37，需明显小于 MAX_UPLOAD_SIZE，
    # 否则请求体会被上游拒收（20MB 图片 base64 后约 27MB，几乎必然失败）。
    AI_MAX_IMAGE_BYTES: int = 4 * 1024 * 1024
    # 一次批改最多送入模型的图片张数（附件图片 + 正文内嵌图片，全局合计）
    AI_MAX_IMAGES: int = 6
    # 图片预缩放的上限边长（像素）。官方每图 token 上限 1024，1300×1300 与 5000×5000
    # 消耗完全相同，原图直送纯浪费；仅在长边超过此值时缩到该值（绝不放大）。
    AI_IMAGE_MAX_SIDE: int = 1600
    # JPEG 编码质量（1-95）。有损压缩大幅减小体积，对模型识别几乎无损。
    AI_IMAGE_JPEG_QUALITY: int = 85
    # 整批图片（data URL）总字节护栏。官方请求体上限 48MiB，base64 后体积约 ×1.37，
    # 故留足余量限制在 24MiB，避免把整条请求撑爆被上游拒收。
    AI_IMAGE_MAX_TOTAL_BYTES: int = 24 * 1024 * 1024
    # 透传给 image_url.detail：original 保留原图，low 缩到 512×512 省 token，
    # auto 当前等价 original。置空字符串则不带该字段。
    AI_IMAGE_DETAIL: str = "original"

    # ---------------- AI 学伴（docs/DESIGN-AI学伴.md） ----------------
    # 单次模型调用超时（秒）。学伴是**同步阻塞**调用（学生当场等回答），与批改的
    # 后台线程范式不同：必须明显小于前端 axios 的 30000ms（``frontend/src/api/request.js``），
    # 否则会出现「后端刚好返回、前端已断连」的最坏状态 —— 后端算成功、额度已扣、
    # 消息已落库，而前端报超时、学生重试 ⇒ 双扣 + 双落库。
    # 压到 25s 即预留 5s 给网络与序列化（连接、TLS、服务端排队、DB、附件抽取）。
    # ⚠️ 因此本值**必须** < 30（前端超时毫秒数换算为秒）；调大前须同步调整前端该接口超时。
    AI_COMPANION_TIMEOUT: int = 25
    # 学伴每日调用次数上限缺省值（**平台池**，与批改的 AI_DEFAULT_DAILY_LIMIT=200 相互独立）。
    # 额度单位不同：批改额度单位是「份提交」（教师一点即 N 份，突发大额、可预估）；
    # 学伴额度单位是「次提问」（学生个体、小额、高频）。学伴使用独立计数表
    # ``ai_usage_daily_companion``，与批改的 ``ai_usage_daily`` 互不挤占（各自的成本刹车）。
    # ⚠️ 本值是**全平台**一天的总次数（成本刹车，跨所有学生），与下方
    # ``AI_COMPANION_DEFAULT_PER_STUDENT_DAILY_LIMIT``（**单个学生**的上限）叠加生效。
    # 6000 ≈ 支撑约 300 个满额学生（6000 / 20），由平台超管在 ``ai_companion_daily_limit``
    # 配置项中按真实用量校准（**保守工程估算起点，非实测最优值**）。
    AI_COMPANION_DEFAULT_DAILY_LIMIT: int = 6000
    # 每个学生的 AI 学伴每日次数上限缺省值（docs/DESIGN-AI学伴配额.md D3）。
    # 与平台池 ``AI_COMPANION_DEFAULT_DAILY_LIMIT`` **语义/单位/量级都不同**：
    # 平台池 = 全平台成本刹车；本值 = 单个学生的公平性上限。二者**叠加生效（双闸门）**。
    # 20 为保守工程估算（非实测）：一次正常作业求助约 3–8 次问答即足够，20 给足 2–3 轮
    # 卡壳余量，同时挡住「把学伴当搜索引擎刷」的滥用。由超管在
    # ``ai_companion_per_student_daily_limit`` 配置项按用量校准。
    # ⚠️ 需与平台池保持量级协调：平台池缺省 / 本值 ≈ 可满额使用的学生数（6000 / 20 ≈ 300）。
    AI_COMPANION_DEFAULT_PER_STUDENT_DAILY_LIMIT: int = 20

    # CORS：默认放行本地开发端口，生产通过环境变量收敛（逗号分隔或 JSON 列表）
    CORS_ORIGINS: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # 是否信任反向代理传来的 `X-Forwarded-For`（用于按**真实客户端 IP** 限流）。
    # ⚠️ 默认 False。该头可被客户端伪造：只有部署在**自己可控的**反向代理之后、
    # 且代理会重写该头时才可开启，否则攻击者可伪造 IP 绕过 / 干扰限流计数。
    TRUST_PROXY_HEADERS: bool = False

    # ---------------- 认证接口限流（slowapi） ----------------
    # 限流是**按客户端 IP 计数**的。校园网 / 机房 / 企业出口普遍是 NAT 共享 IP，
    # 几十上百名师生从同一 IP 登录会互相挤占配额 —— 阈值定得太小，第六个登录的人
    # 就会收到 429「操作过于频繁」。因此这里把阈值放宽到「一个人一天正常操作也远远
    # 用不完」的量级；防爆破的主力仍是**账号维度**的失败锁定（5 次错口令锁 15 分钟，
    # 见 auth_service.MAX_FAILED_ATTEMPTS），IP 限流只兜底「同一出口高频轮询」。
    # 这些值均可通过环境变量覆盖，部署到不同规模的环境时无需改代码。
    AUTH_LOGIN_RATE_LIMIT: str = "30/minute"       # 登录
    AUTH_REGISTER_RATE_LIMIT: str = "30/minute"    # 学生自助注册
    AUTH_REFRESH_RATE_LIMIT: str = "120/minute"    # 刷新令牌（前端静默续期，调用最频繁）
    AUTH_LOGOUT_RATE_LIMIT: str = "60/minute"      # 登出

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
