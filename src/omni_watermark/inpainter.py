from __future__ import annotations

import gc
from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class InpaintConfig:
    telea_radius: int = 3
    batch_size: int = 4
    device: str = "auto"


class FastInpainter:
    def __init__(self, config: InpaintConfig | None = None):
        self.cfg = config or InpaintConfig()

    def inpaint(self, frame, mask):
        if frame is None or mask is None:
            raise ValueError("frame and mask are required")
        if frame.shape[:2] != mask.shape[:2]:
            raise ValueError("Frame/mask dimensions differ")
        m = (mask > 0).astype(np.uint8) * 255
        return (
            frame.copy()
            if not np.any(m)
            else cv2.inpaint(
                frame, m, max(1, self.cfg.telea_radius), cv2.INPAINT_TELEA
            )
        )

    def inpaint_batch(
        self, frames: Sequence[np.ndarray], masks: Sequence[np.ndarray]
    ):
        if len(frames) != len(masks):
            raise ValueError("frames/masks length mismatch")
        return [self.inpaint(frame, mask) for frame, mask in zip(frames, masks)]


class AIInpainter:
    """Explicit sequence-runner boundary for ProPainter/LaMa integrations."""

    def __init__(self, command, config: InpaintConfig | None = None):
        if not command:
            raise ValueError("AI command is required")
        self.command = list(command)
        self.cfg = config or InpaintConfig()

    def inpaint_batch(self, frames, masks):
        raise NotImplementedError(
            "Attach a project-specific ProPainter/LaMa sequence runner"
        )


class Inpainter:
    def __init__(self, engine="fast", config=None, ai_backend=None):
        if engine not in {"fast", "ai"}:
            raise ValueError("engine must be fast or ai")
        self.engine = engine
        self.fast = FastInpainter(config)
        self.ai = ai_backend

    def process_batch(self, frames, masks):
        if self.engine == "fast":
            return self.fast.inpaint_batch(frames, masks)
        if self.ai is None:
            raise RuntimeError("AI engine selected without backend")
        try:
            return self.ai.inpaint_batch(frames, masks)
        except RuntimeError as exc:
            self.release_memory()
            if "out of memory" in str(exc).lower():
                raise MemoryError("GPU OOM; reduce --batch-size") from exc
            raise

    @staticmethod
    def release_memory():
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except ImportError:
            pass
