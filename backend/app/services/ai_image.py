"""图片预处理管线（AI 批改多模态输入的前置处理）。

本模块是**纯图片处理**，不得 import `ai_attachments`（避免循环导入）。
调用方（`ai_attachments`）传入磁盘绝对路径，本模块负责：

1. 按**字节内容**嗅探真实格式（不看文件名 / MIME），因为 DeepSeek 视觉接口
   只接受 JPEG / PNG / GIF / WebP，且以文件实际内容判定；
2. 客户端预缩放：官方每图 token 上限 1024，1300×1300 与 5000×5000 的图消耗**完全相同**，
   原图直送纯浪费带宽与 token，故在边长超过 `max_side` 时缩到 `max_side`（**绝不放大**）；
3. EXIF 方向摆正：手机照片常横躺（Orientation 元数据），不摆正会显著拉低手写字识别率；
4. 透明通道保留：源图含透明（RGBA/LA/带 transparency 的 P）则输出 PNG，否则转 JPEG。

模块契约：**永不抛异常、永不阻塞批改**。任何一步失败都返回 `(None, 简短中文原因)`，
让上层把该图降级为「未参与批改」，而不是让整份作业的批改失败。
"""
import base64
import logging
import os

logger = logging.getLogger("teachhub.ai")

# DeepSeek 视觉接口原生支持的 4 种格式（由文件内容判定，不看扩展名）
SUPPORTED_FORMATS = ("jpeg", "png", "gif", "webp")


def sniff_format(raw: bytes) -> str | None:
    """按魔数判定图片真实格式，返回小写规范名；未知返回 None。

    规范名与 Pillow 的 mode/format 对齐（jpeg/png/gif/webp/bmp/heic/heif/avif），
    供 `prepare_data_url` 决定是否支持，以及（Pillow 缺失降级时）拼 MIME 用。
    """
    if len(raw) < 12:
        return None

    # JPEG: ff d8 ff
    if raw[:3] == b"\xff\xd8\xff":
        return "jpeg"
    # PNG: 89 50 4e 47 0d 0a 1a 0a
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    # GIF: GIF87a / GIF89a
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    # WebP: RIFF....WEBP （偏移 0 起 RIFF，偏移 8 起 WEBP）
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    # BMP: 42 4d ("BM")
    if raw[:2] == b"BM":
        return "bmp"
    # HEIC / HEIF / AVIF: ISOBMFF 文件以 4 字节 box 长度开头，偏移 4 起是 `ftyp` box，
    # 偏移 8 起的 4 字节 major brand 标识具体格式：
    #   heic/heix  → HEIF (HEVC)
    #   mif1/msf1  → HEIF
    #   avif       → AVIF
    if raw[4:8] == b"ftyp":
        brand = raw[8:12]
        if brand in (b"heic", b"heix", b"hevc", b"hevx"):
            return "heic"
        if brand in (b"mif1", b"msf1"):
            return "heif"
        if brand == b"avif":
            return "avif"
    return None


def prepare_data_url(
    path: str,
    *,
    max_bytes: int,
    max_side: int,
    jpeg_quality: int,
) -> tuple[str | None, str]:
    """把磁盘图片处理成可送入多模态的 data URL。

    返回 ``(data_url, "")``（成功）或 ``(None, 简短中文原因)``（失败）。**永不抛异常**。

    处理步骤：
      1. stat 大小 → 超 `max_bytes` 直接拒绝；
      2. 读字节、嗅探真实格式 → 不支持（BMP/HEIC/HEIF/AVIF/未知）给出精确原因；
      3. 延迟 import Pillow；不可用时**降级**为「嗅探格式 → 原始 base64」直接送出，
         保证「永不阻塞批改」契约（warning 一次）；
      4. 有 Pillow 时：打开 → EXIF 摆正 → 决定输出格式（含透明则 PNG，否则 JPEG）
         → 仅在长边 > max_side 时缩放到 max_side（绝不放大）→ 编码；
         若仍超 max_bytes，降到 quality 70 + 边长减半再试一次；仍超则拒绝。

    Args:
        path: 图片绝对路径。
        max_bytes: 单图字节上限（data URL 之前的体积）。
        max_side: 缩放宽高上限（像素），仅缩小不放大。
        jpeg_quality: JPEG 编码质量（1-95）。
    """
    try:
        size = os.path.getsize(path)
    except OSError:
        return None, "无法读取文件"
    if size > max_bytes:
        return None, f"图片过大（>{max_bytes // (1024 * 1024)}MB）"

    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None, "无法读取文件"

    fmt = sniff_format(raw)
    if fmt is None:
        return None, "无法识别的图片格式"
    if fmt == "bmp":
        return None, "BMP 不受模型支持，请转为 JPEG/PNG"
    if fmt in ("heic", "heif", "avif"):
        return None, f"{fmt.upper()} 不受模型支持，请转为 JPEG/PNG"
    if fmt not in SUPPORTED_FORMATS:
        # 已知但不支持的其它格式（理论上不会到这，sniff 只返回上述集合）
        return None, f"{fmt.upper()} 不受模型支持，请转为 JPEG/PNG"

    # 延迟导入 Pillow：缺失只影响图片处理，不影响服务启动与其它格式解析
    try:
        from io import BytesIO

        from PIL import Image, ImageOps
    except ImportError:
        # 降级：Pillow 不可用时，用嗅探出的格式拼原始 base64 data URL 直接送出。
        # 仍遵守「永不抛异常、永不阻塞批改」契约——模型能看原始字节，
        # 只是放弃了缩放 / EXIF 摆正 / 透明保留等优化。
        logger.warning("Pillow 未安装，图片降级为原始字节直送（无缩放/EXIF 摆正）：%s", path)
        encoded = base64.b64encode(raw).decode("ascii")
        mime = {
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }[fmt]
        return f"data:{mime};base64,{encoded}", ""

    try:
        img = Image.open(BytesIO(raw))
        # EXIF 方向摆正：手机照片常因 Orientation 元数据横躺，显著拉低识别率。
        # 摆正失败（极少数损坏/极端小图）不阻断——保留原图继续处理，最坏只是方向未校正。
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            logger.debug("EXIF 方向摆正失败，退回原图继续处理：%s", path)

        # 决定输出格式：含透明通道 → PNG 保透明；否则 JPEG 省体积
        has_transparency = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info
        )
        out_format = "PNG" if has_transparency else "JPEG"

        # 动图（GIF/WebP 多帧）取首帧按静态图处理
        if getattr(img, "is_animated", False):
            try:
                img.seek(0)
            except (EOFError, ValueError):
                pass

        # 预缩放不损失模型信息：官方每图 token 上限 1024，
        # 1300×1300 与 5000×5000 的图消耗完全相同，原图直送纯浪费。
        # 仅在长边超过 max_side 时缩放（绝不放大）。
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side), Image.LANCZOS)

        buffer = BytesIO()
        save_kwargs = {}
        if out_format == "JPEG":
            if img.mode != "RGB":
                img = img.convert("RGB")
            save_kwargs["quality"] = jpeg_quality
            save_kwargs["optimize"] = True
        img.save(buffer, format=out_format, **save_kwargs)
        data = buffer.getvalue()

        # 仍超上限：降一档再试一次（质量 70 + 边长减半）
        if len(data) > max_bytes:
            # 降一档再试一次：JPEG 同时降质量 + 缩边长；PNG 只能靠缩边长。
            # 注意必须改写 save_kwargs（而非只改局部变量），否则质量根本不会降。
            if out_format == "JPEG":
                save_kwargs["quality"] = min(jpeg_quality, 70)
            side = max(1, max_side // 2)
            if max(img.size) > side:
                img.thumbnail((side, side), Image.LANCZOS)
            buffer = BytesIO()
            img.save(buffer, format=out_format, **save_kwargs)
            data = buffer.getvalue()

        if len(data) > max_bytes:
            return None, f"图片过大（压缩后仍超过 {max_bytes // (1024 * 1024)}MB）"

        encoded = base64.b64encode(data).decode("ascii")
        mime = "image/png" if out_format == "PNG" else "image/jpeg"
        return f"data:{mime};base64,{encoded}", ""
    except Exception:
        logger.exception("图片处理失败（降级为未参与批改）：%s", path)
        return None, "图片处理失败"
