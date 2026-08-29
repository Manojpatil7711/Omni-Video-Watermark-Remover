from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np


class TemporalCommandInpainter:
    """Run an external ProPainter/LaMa-compatible sequence command.

    The command receives an input-frame directory and mask directory plus an
    output directory. This keeps heavyweight model implementations optional
    while providing a stable production integration boundary.
    """

    def __init__(self, command: Sequence[str], work_dir: str | None = None):
        if not command:
            raise ValueError("AI command is required")
        self.command = list(command)
        self.work_dir = work_dir

    def inpaint_batch(
        self, frames: Sequence[np.ndarray], masks: Sequence[np.ndarray]
    ) -> list[np.ndarray]:
        if len(frames) != len(masks):
            raise ValueError("frames/masks length mismatch")
        if not frames:
            return []

        with tempfile.TemporaryDirectory(dir=self.work_dir) as tmp:
            root = Path(tmp)
            frames_dir = root / "frames"
            masks_dir = root / "masks"
            output_dir = root / "output"
            frames_dir.mkdir()
            masks_dir.mkdir()
            output_dir.mkdir()

            for index, (frame, mask) in enumerate(zip(frames, masks)):
                if frame is None or mask is None:
                    raise ValueError("frame and mask are required")
                if frame.shape[:2] != mask.shape[:2]:
                    raise ValueError("Frame/mask dimensions differ")
                if not cv2.imwrite(str(frames_dir / f"{index:06d}.png"), frame):
                    raise OSError(f"Failed to write frame {index}")
                binary = (mask > 0).astype(np.uint8) * 255
                if not cv2.imwrite(str(masks_dir / f"{index:06d}.png"), binary):
                    raise OSError(f"Failed to write mask {index}")

            command = self.command + [
                "--input-dir",
                str(frames_dir),
                "--mask-dir",
                str(masks_dir),
                "--output-dir",
                str(output_dir),
            ]
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip()
                raise RuntimeError(
                    f"Temporal AI backend failed ({result.returncode}): {detail}"
                )

            output: list[np.ndarray] = []
            for index in range(len(frames)):
                path = output_dir / f"{index:06d}.png"
                image = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if image is None:
                    raise RuntimeError(f"Temporal AI backend missed output: {path}")
                output.append(image)
            return output
