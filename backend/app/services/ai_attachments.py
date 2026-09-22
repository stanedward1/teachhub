"""作业提交附件的文本抽取（AI 批改输入的一部分）。

设计原则：**永不抛异常、永不阻塞批改**。任何解析失败（缺库、格式不支持、文件不存在、
编码异常、文件过大）都降级为「该附件未参与批改」，并把原因写进 ``note``，
最终落到 `ai_grading_results.attachment_used` 供教师查看。

支持范围（P0，对应 docs/AI-GRADING-PRD.md §8 Q4「附件纳入批改」）：

- 纯文本类（.txt/.md/.csv/.json 及常见代码后缀）→ 直接读取，编码容错；
- Word（.docx）→ python-docx 抽取段落文本；
- PDF（.pdf）→ pypdf 抽取前若干页文本；
- 图片类（.jpg/.jpeg/.png/.gif/.webp/.bmp）→ **仅在凭证开启 `vision_enabled` 时**
  以 base64 data URL 形式随消息送入多模态；未开启则标注跳过（不报错）；
- 其它（.zip/.doc/.xls 等二进制格式）→ 标注暂不支持。

依赖延迟导入：解析库缺失只影响对应格式，不影响服务启动与其它格式解析。
"""
import base64
import logging
import os
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger("teachhub.ai")

# 可直读的纯文本类扩展名
TEXT_EXTS = {
    ".txt", ".md", ".csv", ".json", ".log", ".xml", ".yml", ".yaml",
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".cs", ".go", ".rs",
    ".html", ".css", ".sql", ".sh", ".bat",
}
# 走多模态的图片类扩展名 → MIME
IMAGE_EXTS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

# PDF 最多解析页数（避免超长文档拖垮调用）
_PDF_MAX_PAGES = 20


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


def _image_data_url(path: str, ext: str) -> tuple[str | None, str]:
    """把图片转成 data URL。返回 (data_url | None, 失败原因)。"""
    try:
        size = os.path.getsize(path)
    except OSError:
        return None, "无法读取文件"
    if size > settings.MAX_UPLOAD_SIZE:
        return None, "图片过大"
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None, "无法读取文件"
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{IMAGE_EXTS[ext]};base64,{encoded}", ""


def extract_attachment(
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
        elif ext in IMAGE_EXTS:
            if not vision_enabled:
                return AttachmentPayload(
                    note=f"图片附件未参与批改：未启用多模态（{display}）"
                )
            data_url, reason = _image_data_url(path, ext)
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
