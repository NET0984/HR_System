"""Phát hiện và căn chỉnh khuôn mặt bằng YuNet (OpenCV)."""

import cv2
import numpy as np
from django.conf import settings

# 5 điểm mốc chuẩn của ArcFace trên ảnh 112x112.
ARCFACE_TEMPLATE = np.array([
    [38.2946, 51.6963],
    [73.5318, 51.5014],
    [56.0252, 71.7366],
    [41.5493, 92.3655],
    [70.7299, 92.2041],
], dtype=np.float32)

_detector = None


def models_available():
    return (
        (settings.FACE_MODEL_DIR / 'face_detection_yunet_2023mar.onnx').exists()
        and (settings.FACE_MODEL_DIR / 'w600k_r50.onnx').exists()
    )


def _get_detector():
    global _detector
    if _detector is None:
        path = str(settings.FACE_MODEL_DIR / 'face_detection_yunet_2023mar.onnx')
        _detector = cv2.FaceDetectorYN.create(path, '', (320, 320), 0.6, 0.3, 5000)
    return _detector


def detect_and_align(image_bgr):
    """Trả về ảnh 112x112 đã căn chỉnh, hoặc None nếu không thấy mặt."""
    detector = _get_detector()
    height, width = image_bgr.shape[:2]
    detector.setInputSize((width, height))
    _retval, faces = detector.detect(image_bgr)
    if faces is None or len(faces) == 0:
        return None

    face = max(faces, key=lambda item: item[2] * item[3])
    # YuNet trả về 5 điểm theo thứ tự trùng với template ArcFace
    # (mắt trái, mắt phải, mũi, miệng trái, miệng phải theo hướng nhìn ảnh).
    landmarks = face[4:14].reshape(5, 2).astype(np.float32)

    matrix, _inliers = cv2.estimateAffinePartial2D(
        landmarks, ARCFACE_TEMPLATE, method=cv2.LMEDS,
    )
    if matrix is None:
        return None
    return cv2.warpAffine(image_bgr, matrix, (112, 112), borderValue=0.0)
