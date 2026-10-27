"""Average hash (aHash) dùng cho mô phỏng so khớp ảnh khuôn mặt."""

from PIL import Image, ImageOps

HASH_SIZE = 8
HASH_HEX_LENGTH = HASH_SIZE * HASH_SIZE // 4


def average_hash_image(image) -> str:
    """Tính average hash 64 bit từ một đối tượng ảnh Pillow."""
    grey = image.convert('L').resize(
        (HASH_SIZE, HASH_SIZE),
        Image.Resampling.LANCZOS,
    )
    pixels = list(grey.getdata())

    if not pixels:
        raise ValueError('Ảnh rỗng.')

    average = sum(pixels) / len(pixels)
    bits = 0
    for pixel in pixels:
        bits = (bits << 1) | (1 if pixel > average else 0)
    return f'{bits:0{HASH_HEX_LENGTH}x}'


def average_hash(file_obj) -> str:
    """Tính average hash 64 bit, trả về chuỗi hex 16 ký tự."""
    file_obj.seek(0)
    with Image.open(file_obj) as image:
        return average_hash_image(ImageOps.exif_transpose(image))


def hamming_similarity(hash_a: str, hash_b: str) -> float:
    """Độ tương đồng từ 0 đến 1 giữa hai hash hex cùng độ dài."""
    if not hash_a or not hash_b or len(hash_a) != len(hash_b):
        return 0.0
    try:
        distance = bin(int(hash_a, 16) ^ int(hash_b, 16)).count('1')
    except ValueError:
        return 0.0
    return 1.0 - distance / (len(hash_a) * 4)
