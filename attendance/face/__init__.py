"""Mô phỏng xác thực khuôn mặt cho chấm công.

Ưu tiên ArcFace embedding (ONNX) nếu có model; nếu không thì dùng
average hash. Toàn bộ ảnh được xử lý trong bộ nhớ và không được lưu lại.
"""

from .augment import variant_hashes, variant_samples
from .detector import models_available
from .hashing import average_hash, hamming_similarity
from .service import cosine_similarity, verify_employee_face

__all__ = [
    'average_hash',
    'hamming_similarity',
    'cosine_similarity',
    'models_available',
    'verify_employee_face',
    'variant_hashes',
    'variant_samples',
]
