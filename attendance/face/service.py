"""Xác thực khuôn mặt cho một nhân viên.

Dùng ArcFace embedding nếu có model; nếu không, quay về average hash.
"""

import numpy as np
from django.conf import settings

from .detector import detect_and_align, models_available
from .embedder import embed_aligned
from .hashing import average_hash, hamming_similarity


def cosine_similarity(vector_a, vector_b):
    array_a = np.asarray(vector_a, dtype=np.float32)
    array_b = np.asarray(vector_b, dtype=np.float32)
    if array_a.shape != array_b.shape or array_a.size == 0:
        return 0.0
    denominator = float(np.linalg.norm(array_a) * np.linalg.norm(array_b))
    if denominator == 0:
        return 0.0
    return float(np.dot(array_a, array_b) / denominator)


def _read_bgr(file_obj):
    import cv2
    file_obj.seek(0)
    data = np.frombuffer(file_obj.read(), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _use_embeddings(samples):
    if settings.FACE_ENGINE == 'hash':
        return False
    if not models_available():
        return False
    return any(sample.embedding for sample in samples)


def verify_employee_face(employee, file_obj):
    """So khớp ảnh chụp với tất cả mẫu đã đăng ký.

    Trả về (accepted, score, status, engine) với status là 'ok',
    'not_enrolled', 'invalid_image' hoặc 'no_face'.
    """
    profile = getattr(employee, 'face_profile', None)
    if profile is None or not profile.is_active:
        return False, 0.0, 'not_enrolled', ''

    samples = list(profile.samples.all())
    if not samples:
        return False, 0.0, 'not_enrolled', ''

    if _use_embeddings(samples):
        try:
            image = _read_bgr(file_obj)
            if image is None:
                return False, 0.0, 'invalid_image', 'arcface'
            aligned = detect_and_align(image)
            if aligned is None:
                return False, 0.0, 'no_face', 'arcface'
            candidate = embed_aligned(aligned)
            if candidate is None:
                return False, 0.0, 'invalid_image', 'arcface'
        except Exception:
            return False, 0.0, 'invalid_image', 'arcface'

        score = max(
            (cosine_similarity(candidate, sample.embedding)
             for sample in samples if sample.embedding),
            default=0.0,
        )
        score = max(0.0, min(1.0, score))
        return score >= settings.FACE_EMBEDDING_THRESHOLD, score, 'ok', 'arcface'

    try:
        candidate_hash = average_hash(file_obj)
    except Exception:
        return False, 0.0, 'invalid_image', 'hash'

    score = max(
        (hamming_similarity(sample.image_hash, candidate_hash) for sample in samples),
        default=0.0,
    )
    return score >= settings.FACE_HASH_THRESHOLD, score, 'ok', 'hash'
