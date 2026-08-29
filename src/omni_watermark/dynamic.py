from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import cv2
import numpy as np

from .detector import Detection


@dataclass(frozen=True)
class Track:
    track_id: int
    label: str
    confidence: float
    bbox: tuple[int, int, int, int]
    mask: np.ndarray


class DynamicBackend:
    """Backend contract for SAM-2, YOLO-World, Florence-2, or custom detectors."""

    def detect(self, frame: np.ndarray) -> list[Detection]:
        raise NotImplementedError


class OpenCVMotionBackend(DynamicBackend):
    """Dependency-light fallback for moving overlay regions.

    This is deliberately conservative: it uses temporal differencing and connected
    components rather than pretending that a generic object detector understands
    watermarks. It is useful for smoke tests and CPU-only deployments.
    """

    def __init__(self, min_area_ratio: float = 0.0002, max_area_ratio: float = 0.15):
        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio
        self._previous: np.ndarray | None = None

    def detect(self, frame: np.ndarray) -> list[Detection]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self._previous is None:
            self._previous = gray
            return []
        diff = cv2.absdiff(self._previous, gray)
        self._previous = gray
        threshold = cv2.threshold(diff, 24, 255, cv2.THRESH_BINARY)[1]
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        threshold = cv2.morphologyEx(threshold, cv2.MORPH_CLOSE, kernel)
        threshold = cv2.dilate(threshold, kernel)
        h, w = gray.shape
        total = float(h * w)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(threshold)
        detections: list[Detection] = []
        for index in range(1, count):
            area = float(stats[index, cv2.CC_STAT_AREA]) / total
            if not self.min_area_ratio <= area <= self.max_area_ratio:
                continue
            x = int(stats[index, cv2.CC_STAT_LEFT])
            y = int(stats[index, cv2.CC_STAT_TOP])
            bw = int(stats[index, cv2.CC_STAT_WIDTH])
            bh = int(stats[index, cv2.CC_STAT_HEIGHT])
            mask = np.zeros_like(gray)
            mask[labels == index] = 255
            detections.append(Detection(mask, min(1.0, area * 20.0), (x, y, bw, bh), "motion"))
        return detections


class IoUTracker:
    """Small deterministic IoU tracker for per-frame watermark masks.

    For high-end deployments, replace the association layer with ByteTrack while
    keeping the Track representation unchanged.
    """

    def __init__(self, iou_threshold: float = 0.25, max_age: int = 12):
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self._next_id = 1
        self._tracks: dict[int, tuple[tuple[int, int, int, int], int]] = {}

    @staticmethod
    def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        x1, y1 = max(ax, bx), max(ay, by)
        x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        union = aw * ah + bw * bh - inter
        return inter / union if union else 0.0

    def update(self, detections: Sequence[Detection]) -> list[Track]:
        current: dict[int, tuple[tuple[int, int, int, int], int]] = {}
        used: set[int] = set()
        result: list[Track] = []
        for detection in detections:
            if detection.bbox is None:
                continue
            best_id, best_score = None, 0.0
            for track_id, (bbox, age) in self._tracks.items():
                if track_id in used:
                    continue
                score = self._iou(bbox, detection.bbox)
                if score > best_score:
                    best_id, best_score = track_id, score
            if best_id is None or best_score < self.iou_threshold:
                best_id = self._next_id
                self._next_id += 1
            used.add(best_id)
            current[best_id] = (detection.bbox, 0)
            result.append(
                Track(best_id, detection.label, detection.confidence, detection.bbox, detection.mask)
            )
        for track_id, (bbox, age) in self._tracks.items():
            if track_id not in current and age + 1 <= self.max_age:
                current[track_id] = (bbox, age + 1)
        self._tracks = current
        return result


def merge_track_masks(tracks: Iterable[Track], shape: tuple[int, int]) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    for track in tracks:
        if track.mask.shape[:2] != shape:
            raise ValueError("Track mask dimensions differ from frame")
        mask = cv2.bitwise_or(mask, track.mask.astype(np.uint8))
    return mask
