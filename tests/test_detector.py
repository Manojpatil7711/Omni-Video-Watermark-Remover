import cv2
import numpy as np
from omni_watermark.detector import StaticDetector, StaticDetectorConfig


def test_static_detector_returns_mask():
    frames = []
    for _ in range(8):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        cv2.rectangle(frame, (5, 5), (35, 25), (255, 255, 255), -1)
        frames.append(frame)
    result = StaticDetector(
        StaticDetectorConfig(edge_percentile=70, min_area_ratio=0.0001)
    ).detect(frames)
    assert result.mask.shape == (120, 160)
    assert result.mask.dtype == np.uint8
