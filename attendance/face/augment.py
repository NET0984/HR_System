"""Sinh biến thể ảnh cho đăng ký khuôn mặt (augmentation).

Ảnh được thu nhỏ trước khi sinh biến thể để tránh xử lý ảnh độ phân giải lớn.
Chỉ dùng các phép biến đổi làm thay đổi bố cục sáng/tối của ảnh.
Không dùng tăng/giảm độ sáng vì average hash so với trung bình ảnh,
nên thay đổi độ sáng đều không làm hash thay đổi.
"""

import cv2
import numpy as np
from PIL import Image, ImageOps

from .hashing import average_hash_image

MAX_SIDE = 640

VARIANTS = (
    'original',
    'flip',
    'rotate_left',
    'rotate_right',
    'zoom_in',
    'zoom_out',
)

# Chỉ tính embedding cho các biến thể thực sự hữu ích; các biến thể còn lại
# vẫn được lưu hash để dùng cho chế độ so khớp ảnh dự phòng.
EMBEDDED_VARIANTS = ('original', 'flip', 'rotate_left')


def _rotate(image, angle):
    return image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)


def _zoom_in(image):
    width, height = image.size
    margin_x = max(1, int(width * 0.06))
    margin_y = max(1, int(height * 0.06))
    return image.crop((margin_x, margin_y, width - margin_x, height - margin_y))


def _zoom_out(image):
    width, height = image.size
    pad_x = max(1, int(width * 0.06))
    pad_y = max(1, int(height * 0.06))
    canvas = Image.new('RGB', (width + 2 * pad_x, height + 2 * pad_y), (128, 128, 128))
    canvas.paste(image, (pad_x, pad_y))
    return canvas


def prepare_image(image):
    """Chuẩn hoá ảnh và thu nhỏ cạnh dài về tối đa MAX_SIDE."""
    base = ImageOps.exif_transpose(image).convert('RGB')
    base.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    return base


def build_variants(base):
    """Trả về danh sách (tên biến thể, ảnh Pillow) từ ảnh đã chuẩn hoá."""
    return [
        ('original', base),
        ('flip', ImageOps.mirror(base)),
        ('rotate_left', _rotate(base, -6)),
        ('rotate_right', _rotate(base, 6)),
        ('zoom_in', _zoom_in(base)),
        ('zoom_out', _zoom_out(base)),
    ]


def _pil_to_bgr(image):
    rgb = np.array(image.convert('RGB'))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _rotate_aligned(image, angle):
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (width, height), borderMode=cv2.BORDER_REPLICATE,
    )


def _transform_aligned(aligned, variant):
    if variant == 'flip':
        return cv2.flip(aligned, 1)
    if variant == 'rotate_left':
        return _rotate_aligned(aligned, -6)
    if variant == 'rotate_right':
        return _rotate_aligned(aligned, 6)
    return aligned


def variant_hashes(file_obj):
    """Trả về danh sách (variant, hash), bỏ các hash trùng nhau."""
    return [
        (variant, image_hash)
        for variant, image_hash, _embedding in variant_samples(file_obj, use_embeddings=False)
    ]


def variant_samples(file_obj, use_embeddings=False):
    """Trả về danh sách (variant, hash, embedding hoặc None)."""
    from .detector import detect_and_align
    from .embedder import embed_aligned

    file_obj.seek(0)
    with Image.open(file_obj) as image:
        image.load()
        base = prepare_image(image)

    aligned = None
    if use_embeddings:
        try:
            aligned = detect_and_align(_pil_to_bgr(base))
        except Exception:
            aligned = None

    samples = {}
    for variant, variant_image in build_variants(base):
        image_hash = average_hash_image(variant_image)
        if image_hash in samples:
            continue

        embedding = None
        if aligned is not None and variant in EMBEDDED_VARIANTS:
            try:
                vector = embed_aligned(_transform_aligned(aligned, variant))
                if vector is not None:
                    embedding = [float(value) for value in vector]
            except Exception:
                embedding = None

        samples[image_hash] = (variant, embedding)

    return [
        (variant, image_hash, embedding)
        for image_hash, (variant, embedding) in samples.items()
    ]
