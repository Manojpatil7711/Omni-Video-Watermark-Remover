from __future__ import annotations

import gc
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SAM2Config:
    model_id: str = "facebook/sam2.1-hiera-small"
    device: str = "cuda"
    offload_video_to_cpu: bool = True
    offload_state_to_cpu: bool = True
    fill_hole_area: int = 8


class SAM2VideoBackend:
    """Real SAM 2 video-segmentation adapter with lazy model loading."""

    def __init__(self, config: SAM2Config | None = None):
        self.cfg = config or SAM2Config()
        self._predictor: Any = None
        self._state: Any = None

    def _load(self) -> None:
        if self._predictor is not None:
            return
        try:
            import torch
            from sam2.sam2_video_predictor import SAM2VideoPredictor
        except ImportError as exc:
            raise RuntimeError(
                "SAM 2 is not installed. Install the optional AI dependencies "
                "and the official SAM 2 package before using --dynamic-backend sam2."
            ) from exc

        device = self.cfg.device
        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"
        if device not in {"cpu", "cuda", "mps"}:
            raise ValueError(f"Unsupported SAM 2 device: {device}")

        try:
            self._predictor = SAM2VideoPredictor.from_pretrained(
                self.cfg.model_id,
                device=device,
                fill_hole_area=self.cfg.fill_hole_area,
            )
        except TypeError:
            self._predictor = SAM2VideoPredictor.from_pretrained(
                self.cfg.model_id,
                device=device,
            )

    @staticmethod
    def _validate_seed(seed_mask: np.ndarray, video_path: str) -> np.ndarray:
        if seed_mask.ndim != 2:
            raise ValueError("SAM 2 seed mask must be a 2-D array")
        if not Path(video_path).is_file():
            raise FileNotFoundError(video_path)
        mask = (seed_mask > 0).astype(np.uint8) * 255
        if not np.any(mask):
            raise RuntimeError("Dynamic detector produced an empty seed mask")
        return mask

    def segment_video(
        self,
        video_path: str,
        seed_mask: np.ndarray,
        frame_idx: int = 0,
        object_id: int = 1,
    ) -> dict[int, np.ndarray]:
        """Propagate a seed mask and return original-resolution masks by frame."""
        self._load()
        mask = self._validate_seed(seed_mask, video_path)
        self._state = self._predictor.init_state(
            video_path=video_path,
            offload_video_to_cpu=self.cfg.offload_video_to_cpu,
            offload_state_to_cpu=self.cfg.offload_state_to_cpu,
        )
        self._predictor.add_new_mask(
            self._state,
            frame_idx=frame_idx,
            obj_id=object_id,
            mask=mask.astype(bool),
        )

        output: dict[int, np.ndarray] = {}
        for idx, _obj_ids, masks in self._predictor.propagate_in_video(
            self._state,
            start_frame_idx=frame_idx,
        ):
            current = masks[0]
            if hasattr(current, "detach"):
                current = current.detach().float().cpu().numpy()
            current = np.asarray(current).squeeze()
            output[int(idx)] = (current > 0).astype(np.uint8) * 255

        return output

    def close(self) -> None:
        self._state = None
        self._predictor = None
        gc.collect()
        try:
            import torch
        except ImportError:
            return
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
