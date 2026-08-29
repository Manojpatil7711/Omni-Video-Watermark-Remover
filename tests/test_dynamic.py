import cv2
import numpy as np

from omni_watermark.dynamic import IoUTracker, OpenCVMotionBackend, merge_track_masks


def _frame(x: int) -> np.ndarray:
    image = np.zeros((80, 120, 3), dtype=np.uint8)
    cv2.rectangle(image, (x, 20), (x + 16, 36), (255, 255, 255), -1)
    return image


def test_motion_backend_detects_moving_region():
    backend = OpenCVMotionBackend(min_area_ratio=0.0001, max_area_ratio=0.5)
    assert backend.detect(_frame(10)) == []
    detections = backend.detect(_frame(20))
    assert detections
    assert detections[0].bbox is not None


def test_iou_tracker_reuses_track_id():
    backend = OpenCVMotionBackend(min_area_ratio=0.0001, max_area_ratio=0.5)
    tracker = IoUTracker(iou_threshold=0.1)
    backend.detect(_frame(10))
    first = tracker.update(backend.detect(_frame(20)))
    second = tracker.update(backend.detect(_frame(21)))
    assert first and second
    assert first[0].track_id == second[0].track_id


def test_merge_track_masks_preserves_shape():
    mask = np.zeros((20, 30), dtype=np.uint8)
    mask[2:5, 3:8] = 255
    assert merge_track_masks([], (20, 30)).shape == mask.shape
