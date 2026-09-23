"""作业提交附件的文本抽取（AI 批改输入的一部分）。

设计原则：**永不抛异常、永不阻塞批改**。任何解析失败（缺库、格式不支持、文件不存在、
编码异常、文件过大）都降级为「该附件未参与批改」，并把原因写进 ``note``，
最终落到 `ai_grading_results.attachment_used` 供教师查看。

支持范围（P0，对应 docs/AI-GRADING-PRD.md §8 Q4「附件纳入批改」）：

- 纯文本类（.txt/.md/.csv/.json 及常见代码后缀）→ 直接读取，编码容错；
- Word（.docx）→ python-docx 抽取段落文本；
- PDF（.pdf）→ pypdf 抽取前若干页文本；
- 图片类（.jpg/.jpeg/.png/.gif/.webp/.jfif/.jpe）→ **仅在凭证开启 `vision_enabled` 时**
  以 base64 data URL 形式随消息送入多模态；格式按**文件实际内容**嗅探（不看文件名/扩展名），
  只认 JPEG/PNG/GIF/WebP 四种；送入前会**预缩放**（仅当长边超过 `AI_IMAGE_MAX_SIDE` 才缩、
  绝不放大）并**按 EXIF 摆正方向**（手机照片横躺会显著拉低识别率）；BMP/HEIC/HEIF/AVIF/TIFF
  等不支持格式**绝不送入模型**，而是精确说明原因；未开启多模态则标注跳过（不报错）；
- 其它（.zip/.doc/.xls 等二进制格式）→ 标注暂不支持。

此外见 :func:`extract_inline_images` —— 学生用富文本编辑器「上传图片」时，图片会被写成
``submissions.content`` 里的一行 Markdown（形如 ``![图片](/uploads/xxx.png)``），
**不会**落到 ``submissions.filepath``。只读附件字段的批改流程因此完全看不到这张图，
模型只能对着一个无法访问的 URL 猜内容（历史缺陷）。

依赖延迟导入：解析库缺失只影响对应格式，不影响服务启动与其它格式解析。
"""
import logging
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache

from app.config import settings
from app.services.ai_image import prepare_data_url

logger = logging.getLogger("teachhub.ai")

# 可直读的纯文本类扩展名
TEXT_EXTS = {
    ".txt", ".md", ".csv", ".json", ".log", ".xml", ".yml", ".yaml",
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs", ".go", ".rs",
    ".html", ".css", ".sql", ".sh", ".bat",
}
# 尝试按图片处理的扩展名 → 回退 MIME（真正的格式由 `ai_image.sniff_format`
# 按字节内容判定，此处扩展名仅用于「要不要尝试当图片处理」）。新增 .jfif/.jpe，
# **移除 .bmp**（BMP 直送会被上游 400 拒收整条请求）。
IMAGE_EXTS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".jfif": "image/jpeg",
    ".jpe": "image/jpeg",
}
# 明确不受模型支持的图片扩展名：命中即给出精确说明、**绝不送入模型**（避免学生传
# 一张 BMP 就让整份批改 400 失败）。真实格式最终由字节嗅探兜底，这里按扩展名快速拦截。
UNSUPPORTED_IMAGE_EXTS = {".bmp", ".heic", ".heif", ".avif", ".tif", ".tiff"}


def _unsupported_image_reason(ext: str) -> str:
    """不受支持图片扩展名对应的中文说明（教师可见）。"""
    return {
        ".bmp": "BMP 不受模型支持，请转为 JPEG/PNG",
        ".heic": "HEIC 不受模型支持，请转为 JPEG/PNG",
        ".heif": "HEIF 不受模型支持，请转为 JPEG/PNG",
        ".avif": "AVIF 不受模型支持，请转为 JPEG/PNG",
        ".tif": "TIFF 不受模型支持，请转为 JPEG/PNG",
        ".tiff": "TIFF 不受模型支持，请转为 JPEG/PNG",
    }.get(ext, f"{ext} 不受模型支持，请转为 JPEG/PNG")

# PDF 最多解析页数（避免超长文档拖垮调用）
_PDF_MAX_PAGES = 20

# 正文内嵌图片引用：Markdown ``![alt](url)`` 与 HTML ``<img src="url">``。
#   - Markdown 的可选 title（``![x](/a.png "t")``）一并吃掉，避免把 title 误当 url；
#   - HTML 只认 src，属性顺序不限。
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\s*\)")
_HTML_IMAGE_RE = re.compile(
    r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE
)

# 前端上传接口返回的访问前缀（见 uploads.save_upload 的 url 字段）
_UPLOADS_URL_PREFIX = "/uploads/"


@dataclass
class AttachmentPayload:
    """附件解析结果。

    Attributes:
        text: 抽取出的纯文本（会被拼接进 prompt）。
        images: 多模态图片 data URL 列表。
        note: 参与情况说明，写入 `ai_grading_results.attachment_used`。
    """

    text: str = ""
    images: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class InlineImagePayload:
    """正文内嵌图片的抽取结果。

    Attributes:
        text: 把图片引用替换为文字占位后的正文（保留图片出现的位置信息）。
        images: 成功转成 data URL 的图片列表（顺序与正文中的【图片N】一致）。
        notes: 参与情况说明片段（用于拼接 `attachment_used`）。
    """

    text: str = ""
    images: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def absolute_path(filepath: str) -> str:
    """把提交里的相对 filepath 还原成磁盘绝对路径。

    与 `homework_service._remove_upload_files` 同一口径：
    `submissions.filepath` 相对 `settings.UPLOAD_DIR`，前端以 `/uploads/<filepath>` 访问。
    """
    return os.path.join(settings.UPLOAD_DIR, filepath.lstrip("/").replace("/", os.sep))


def _read_text_file(path: str) -> str:
    """读纯文本，编码容错（UTF-8 → GBK → 忽略错误）。"""
    for encoding in ("utf-8", "gbk"):
        try:
            with open(path, "r", encoding=encoding) as fh:
                return fh.read()
        except UnicodeDecodeError:
            continue
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def _extract_docx(path: str) -> str:
    """抽取 .docx 段落文本；缺库时抛 ImportError 由上层降级。"""
    import docx  # 延迟导入

    document = docx.Document(path)
    return "\n".join(p.text for p in document.paragraphs if p.text and p.text.strip())


def _extract_pdf(path: str) -> str:
    """抽取 .pdf 文本（限前 `_PDF_MAX_PAGES` 页）；缺库时抛 ImportError 由上层降级。"""
    from pypdf import PdfReader  # 延迟导入

    reader = PdfReader(path)
    pages = reader.pages[:_PDF_MAX_PAGES]
    return "\n".join((page.extract_text() or "") for page in pages)


def _image_data_url(path: str) -> tuple[str | None, str]:
    """把图片转成 data URL（含格式嗅探 / 缩放 / EXIF 摆正 / 字节护栏）。

    薄包装 `ai_image.prepare_data_url`：只传入绝对路径与全局配置，所有格式判定、缩放、
    不支持格式的精确原因都来自图片管线，避免「用扩展名推 MIME」导致 .jfif / 无后缀 /
    后缀写错的图片被误判为「格式不支持」而静默跳过。返回 ``(data_url | None, 失败原因)``，
    **永不抛异常**（失败原因最终落到 `ai_grading_results.attachment_used` 供教师查看）。
    """
    return prepare_data_url(
        path,
        max_bytes=settings.AI_MAX_IMAGE_BYTES,
        max_side=settings.AI_IMAGE_MAX_SIDE,
        jpeg_quality=settings.AI_IMAGE_JPEG_QUALITY,
    )


def _local_upload_filepath(url: str) -> str | None:
    """把 ``/uploads/xxx.png`` 形式的站内图片地址还原成 `absolute_path` 可用的相对路径。

    只认站内上传目录的地址；外链（http/https/data:）一律返回 None —— 模型侧访问不到
    任意外部 URL，交由服务端下载也不安全。容忍 ``?`` 查询串与 ``#`` 锚点。
    """
    if not url:
        return None
    raw = url.strip().split("#", 1)[0].split("?", 1)[0]
    if not raw.startswith(_UPLOADS_URL_PREFIX):
        return None
    rel = raw[len(_UPLOADS_URL_PREFIX):]
    return rel or None


def extract_inline_images(
    text: str,
    *,
    vision_enabled: bool = False,
    max_images: int | None = None,
) -> InlineImagePayload:
    """抽取正文里内嵌的图片引用，转成可送入多模态的 data URL。

    为什么需要它：学生在提交页用富文本编辑器「上传图片」，图片会被写成 ``content``
    里的一行 Markdown（``![图片](/uploads/xxx.png)``），而 ``submissions.filepath``
    仍为空。只读附件字段的批改流程因此完全看不到图片。

    行为：
      - 命中本地上传图片 → 读盘转 data URL（受 ``AI_MAX_IMAGE_BYTES`` 限制），并把引用
        替换为 ``【图片N：alt】`` 占位，让模型知道此处有图、以及附图顺序；
      - 同一图片重复引用 → 只送一次，占位复用同一序号；
      - 未开启多模态 / 文件缺失 / 体积超限 / 超出张数上限 → 不送图，替换为
        ``【图片未参与批改】`` 并记入 ``notes``（教师可见），**不抛异常**；
      - 外链图片（http(s)、data:）→ 原样保留在正文，不下载、不送模型。

    Args:
        text: 学生提交正文（``submissions.content``）。
        vision_enabled: 凭证是否启用多模态（决定图片是否送入）。
        max_images: 本次最多送入的图片张数；``None`` 时取 ``settings.AI_MAX_IMAGES``。

    Returns:
        `InlineImagePayload`。
    """
    if not text:
        return InlineImagePayload(text=text or "")

    limit = settings.AI_MAX_IMAGES if max_images is None else max_images

    # 按出现位置汇总所有图片引用（Markdown + HTML），保证占位与附图的顺序一致
    matches: list[tuple[int, int, str, str]] = []  # (start, end, alt, url)
    for m in _MD_IMAGE_RE.finditer(text):
        matches.append((m.start(), m.end(), (m.group(1) or "").strip(), m.group(2)))
    for m in _HTML_IMAGE_RE.finditer(text):
        matches.append((m.start(), m.end(), "", m.group(1)))
    matches.sort(key=lambda item: item[0])

    images: list[str] = []
    notes: list[str] = []
    assigned: dict[str, int] = {}  # url → 已分配的图片序号（去重与占位都用它）
    rebuilt: list[str] = []
    cursor = 0

    for start, end, alt, url in matches:
        # 与上一段匹配交叠（如 HTML 里再嵌 Markdown）时跳过，避免重复处理同一段文本
        if start < cursor:
            continue
        rebuilt.append(text[cursor:start])
        cursor = end

        label = alt or "图片"
        rel = _local_upload_filepath(url)
        if rel is None:
            # 外链图片：原样保留（模型看不到也无害，至少不丢信息）
            rebuilt.append(text[start:end])
            continue

        if url in assigned:
            rebuilt.append(f"【图片{assigned[url]}：{label}】")
            continue

        if not vision_enabled:
            notes.append(f"内嵌图片未参与批改：未启用多模态（{rel}）")
            rebuilt.append("【图片未参与批改】")
            continue

        if len(images) >= limit:
            notes.append(f"内嵌图片未参与批改：超出单次上限 {limit} 张（{rel}）")
            rebuilt.append("【图片未参与批改】")
            continue

        ext = os.path.splitext(rel)[1].lower()
        path = absolute_path(rel)
        if ext in UNSUPPORTED_IMAGE_EXTS:
            # 命中明确不支持的格式：精确说明、绝不送入模型（否则学生传 BMP 会让整份批改 400）
            notes.append(f"内嵌图片未参与批改：{_unsupported_image_reason(ext)}（{rel}）")
            rebuilt.append("【图片未参与批改】")
            continue
        if ext not in IMAGE_EXTS or not os.path.exists(path):
            notes.append(f"内嵌图片未参与批改：文件不存在或格式不支持（{rel}）")
            rebuilt.append("【图片未参与批改】")
            continue

        data_url, reason = _image_data_url(path)
        if data_url is None:
            notes.append(f"内嵌图片未参与批改：{reason}（{rel}）")
            rebuilt.append("【图片未参与批改】")
            continue

        images.append(data_url)
        assigned[url] = len(images)
        notes.append(f"已纳入内嵌图片（{rel}）")
        rebuilt.append(f"【图片{assigned[url]}：{label}】")

    rebuilt.append(text[cursor:])
    return InlineImagePayload(text="".join(rebuilt), images=images, notes=notes)


# ---------------- 抽取结果缓存（批内复用） ----------------
# 批改一个班时，**同一份任务附件**会随每一份提交被重复抽取：40 份 = 40 次读盘 +
# 40 次 docx/pdf 解析（图片则是 40 次缩放 + base64 编码）。
#
# token 侧的那份重复由上游前缀缓存兜住（DeepSeek 对重复前缀自动按 cache-hit 计价），
# 但**本地这份开销没人兜**：它吃 CPU 与磁盘 IO，并随班级人数线性放大。
#
# 因此只对**批内复用**的附件开启（`cache=True`，当前仅任务附件）。学生提交附件每份都
# 不同，缓存零收益，还会把 N 份图片 data URL 留在内存里 —— 故默认关闭。
_ATTACHMENT_CACHE_MAXSIZE = 32


def _file_stamp(path: str) -> tuple[int, int] | None:
    """文件的 ``(mtime_ns, size)`` 指纹；文件不存在返回 ``None``。

    作为缓存键的一部分：文件被重新上传 / 覆盖同名文件时指纹变化 → 缓存自动失效，
    无需手工清理，也不会读到旧内容。纳秒精度是为了排除「同一秒内替换」的漏判。

    注意「先不存在、后出现」的情形也靠它自愈：缺失时键里是 ``None``，
    文件出现后变成本指纹，键不同 → 重新抽取，不会把「文件不存在」的结论缓存住。
    """
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def _config_fingerprint() -> tuple[int, int, int, int]:
    """影响抽取结果的配置项（截断上限 / 图片字节与尺寸护栏）。

    放进缓存键是为了「改了配置立即生效」—— 否则调大 `AI_MAX_ATTACHMENT_CHARS`
    之后，旧结果会一直命中「已截断」的版本。
    """
    return (
        settings.AI_MAX_ATTACHMENT_CHARS,
        settings.AI_MAX_IMAGE_BYTES,
        settings.AI_IMAGE_MAX_SIDE,
        settings.AI_IMAGE_JPEG_QUALITY,
    )


@lru_cache(maxsize=_ATTACHMENT_CACHE_MAXSIZE)
def _cached_extract(
    key: tuple[str, str, bool, tuple[int, int] | None, tuple[int, ...]],
) -> AttachmentPayload:
    """按 ``key`` 缓存 `_extract_attachment_impl` 的结果。

    参数刻意收成**单个元组**：`lru_cache` 按调用签名建键，``f(a)`` 与
    ``f(a, vision_enabled=False)`` 会被算成两个不同的键 ——
    用单参数可以彻底避免「写法不同就缓存不中」这类静默失效。
    """
    filepath, filename, vision_enabled, _stamp, _config = key
    return _extract_attachment_impl(
        filepath, filename, vision_enabled=vision_enabled
    )


def clear_attachment_cache() -> None:
    """清空附件抽取缓存（供测试与运维使用；正常运行无需调用）。"""
    _cached_extract.cache_clear()


def extract_attachment(
    filepath: str | None,
    filename: str | None = None,
    *,
    vision_enabled: bool = False,
    cache: bool = False,
) -> AttachmentPayload:
    """解析单个附件（本函数负责可选的**批内缓存**，实际抽取见 `_extract_attachment_impl`）。

    Args:
        cache: 是否启用批内缓存。**仅对同一批会重复出现的附件开启**（任务附件）；
            学生提交附件每份都不同，开启只会白占内存。
    """
    if not cache or not filepath:
        return _extract_attachment_impl(filepath, filename, vision_enabled=vision_enabled)

    key = (
        filepath,
        filename or "",
        bool(vision_enabled),
        _file_stamp(absolute_path(filepath)),
        _config_fingerprint(),
    )
    payload = _cached_extract(key)
    # 返回**副本**：缓存对象被多个线程 / 多次调用共享，调用方若就地修改
    # （例如往 `images` 里 append）会污染后续所有命中。浅拷贝即可 —— 字符串本身不可变。
    return AttachmentPayload(
        text=payload.text, images=list(payload.images), note=payload.note
    )


def _extract_attachment_impl(
    filepath: str | None,
    filename: str | None = None,
    *,
    vision_enabled: bool = False,
) -> AttachmentPayload:
    """解析单个附件，返回可送入模型的内容与参与情况说明。

    本函数**不抛异常**：任何失败都转成带说明的空载荷。

    Args:
        filepath: 提交记录里的相对路径（`submissions.filepath`）。
        filename: 原始文件名（用于取扩展名与展示）。
        vision_enabled: 凭证是否启用多模态（决定图片附件是否参与）。

    Returns:
        `AttachmentPayload`。
    """
    if not filepath:
        return AttachmentPayload()

    display = filename or os.path.basename(filepath)
    ext = os.path.splitext(filename or filepath)[1].lower()
    path = absolute_path(filepath)

    if not os.path.exists(path):
        return AttachmentPayload(note=f"附件未参与批改：文件不存在（{display}）")

    try:
        if ext in TEXT_EXTS:
            text = _read_text_file(path)
        elif ext == ".docx":
            text = _extract_docx(path)
        elif ext == ".pdf":
            text = _extract_pdf(path)
        elif ext in IMAGE_EXTS or ext in UNSUPPORTED_IMAGE_EXTS:
            if not vision_enabled:
                return AttachmentPayload(
                    note=f"图片附件未参与批改：未启用多模态（{display}）"
                )
            if ext in UNSUPPORTED_IMAGE_EXTS:
                # 命中明确不支持的格式：精确说明、绝不送入模型（避免 BMP 让整份批改 400）
                return AttachmentPayload(
                    note=f"图片附件未参与批改：{_unsupported_image_reason(ext)}（{display}）"
                )
            data_url, reason = _image_data_url(path)
            if data_url is None:
                return AttachmentPayload(note=f"图片附件未参与批改：{reason}（{display}）")
            return AttachmentPayload(
                images=[data_url], note=f"已纳入图片附件（{display}）"
            )
        else:
            return AttachmentPayload(
                note=f"附件未参与批改：暂不支持 {ext or '未知'} 格式（{display}）"
            )
    except ImportError as exc:
        logger.warning("附件解析库缺失，跳过附件：%s", exc)
        return AttachmentPayload(note=f"附件未参与批改：缺少解析组件（{display}）")
    except Exception:
        logger.exception("附件解析失败，已降级：%s", display)
        return AttachmentPayload(note=f"附件解析失败，未参与批改（{display}）")

    text = (text or "").strip()
    if not text:
        return AttachmentPayload(note=f"附件未参与批改：未抽取到文本（{display}）")

    truncated = len(text) > settings.AI_MAX_ATTACHMENT_CHARS
    if truncated:
        text = text[: settings.AI_MAX_ATTACHMENT_CHARS]

    note = f"已纳入附件：{display}" + ("（超长已截断）" if truncated else "")
    return AttachmentPayload(text=text, note=note)
