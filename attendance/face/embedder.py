"""Trích embedding ArcFace bằng ONNX Runtime."""

import cv2
import numpy as np
import onnxruntime as ort
from django.conf import settings

_session = None
_input_name = None


def _get_session():
    global _session, _input_name
    if _session is None:
        path = str(settings.FACE_MODEL_DIR / 'w600k_r50.onnx')
        _session = ort.InferenceSession(path, providers=['CPUExecutionProvider'])
        _input_name = _session.get_inputs()[0].name
    return _session, _input_name


def embed_aligned(image_bgr):
    """Trả về vector embedding đã chuẩn hoá L2 cho ảnh 112x112."""
    session, input_name = _get_session()
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    rgb = (rgb - 127.5) / 128.0
    blob = np.transpose(rgb, (2, 0, 1))[None, ...]
    output = session.run(None, {input_name: blob})[0][0]
    norm = float(np.linalg.norm(output))
    if norm == 0:
        return None
    return output / norm
