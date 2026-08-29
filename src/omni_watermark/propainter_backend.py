from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

import cv2
import ffmpeg
import numpy as np


class ProPainterBackend:
    """Adapter for the official ProPainter inference CLI.

    The backend keeps ProPainter as an external optional dependency. The
    command should point to ``inference_propainter.py`` (or an equivalent
    wrapper) and its model weights remain outside this repository.
    """

    def __init__(
        self,
        command: Sequence[str],
        work_dir: str | None = None,
        fp16: bool = True,
        width: int | None = None,
        height: int | None = None,
        subvideo_length: int = 80,
        neighbor_length: int = 10,
        ref_stride: int = 10,
    ):
        if not command:
            raise ValueError("ProPainter command is required")
        if subvideo_length < 1:
            raise ValueError("subvideo_length must be >= 1")
        self.command = list(command)
        self.work_dir = work_dir
        self.fp16 = fp16
        self.width = width
        self.height = height
        self.subvideo_length = subvideo_length
        self.neighbor_length = neighbor_length
        self.ref_stride = ref_stride

    def process(
        self,
        frames: Sequence[np.ndarray],
        masks: Sequence[np.ndarray],
        fps: float,
    ) -> list[np.ndarray]:
        if len(frames) != len(masks):
            raise ValueError("frames/masks length mismatch")
        if not frames:
            return []
        if fps <= 0:
            raise ValueError("fps must be positive")

        with tempfile.TemporaryDirectory(dir=self.work_dir) as tmp:
            root = Path(tmp)
            video_path = root / "input.mp4"
            mask_path = root / "mask.png"
            output_dir = root / "results"
            output_dir.mkdir()

            self._write_video(video_path, frames, fps)
            combined = np.zeros_like(masks[0], dtype=np.uint8)
            for mask in masks:
                if mask.shape[:2] != combined.shape[:2]:
                    raise ValueError("Mask dimensions differ")
                combined = cv2.bitwise_or(combined, (mask > 0).astype(np.uint8) * 255)
            if not cv2.imwrite(str(mask_path), combined):
                raise OSError("Failed to write ProPainter mask")

            command = self.command + [
                "--video",
                str(video_path),
                "--mask",
                str(mask_path),
                "--output_dir",
                str(output_dir),
                "--neighbor_length",
                str(self.neighbor_length),
                "--ref_stride",
                str(self.ref_stride),
                "--subvideo_length",
                str(self.subvideo_length),
            ]
            if self.width:
                command.extend(["--width", str(self.width)])
            if self.height:
                command.extend(["--height", str(self.height)])
            if self.fp16:
                command.append("--fp16")

            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip()
                raise RuntimeError(
                    f"ProPainter failed ({result.returncode}): {detail}"
                )

            return self._read_output(output_dir, len(frames))

    @staticmethod
    def _write_video(path: Path, frames: Sequence[np.ndarray], fps: float) -> None:
        height, width = frames[0].shape[:2]
        command = (
            ffmpeg.input("-", format="rawvideo", pix_fmt="bgr24", s=f"{width}x{height}", r=fps)
            .output(str(path), vcodec="libx264", pix_fmt="yuv420p")
            .overwrite_output()
        )
        process = command.run_async(pipe_stdin=True, pipe_stderr=True)
        try:
            for frame in frames:
                if frame.shape[:2] != (height, width):
                    raise ValueError("Frame dimensions differ")
                process.stdin.write(np.ascontiguousarray(frame).tobytes())
            process.stdin.close()
            process.wait()
        except Exception:
            process.kill()
            process.wait()
            raise

    @staticmethod
    def _read_output(output_dir: Path, count: int) -> list[np.ndarray]:
        candidates = sorted(
            p for p in output_dir.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
        )
        if len(candidates) < count:
            raise RuntimeError(
                f"ProPainter produced {len(candidates)} frames; expected {count}"
            )
        result = []
        for path in candidates[:count]:
            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                raise RuntimeError(f"Failed to read ProPainter output: {path}")
            result.append(image)
        return result
