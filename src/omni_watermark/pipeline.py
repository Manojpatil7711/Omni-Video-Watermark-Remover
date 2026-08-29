from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import ffmpeg
import numpy as np
from tqdm import tqdm

from .detector import StaticDetector, StaticDetectorConfig
from .dynamic import IoUTracker, OpenCVMotionBackend, merge_track_masks
from .inpainter import InpaintConfig, Inpainter
from .propainter_backend import ProPainterBackend
from .sam2_backend import SAM2Config, SAM2VideoBackend


@dataclass
class PipelineConfig:
    input: str
    output: str
    mode: str = "static"
    engine: str = "fast"
    gpu_id: int = 0
    batch_size: int = 4
    sample_rate: int = 12
    mask_dilate: int = 3
    telea_radius: int = 3
    device: str = "auto"
    keep_temp: bool = False
    work_dir: str | None = None
    dynamic_backend: str = "opencv"
    sam2_model_id: str = "facebook/sam2.1-hiera-small"
    propainter_command: tuple[str, ...] | None = None
    propainter_fp16: bool = True
    propainter_width: int | None = None
    propainter_height: int | None = None
    propainter_subvideo_length: int = 80
    propainter_neighbor_length: int = 10
    propainter_ref_stride: int = 10


class VideoPipeline:
    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg
        self._validate()
        self.work = Path(cfg.work_dir or tempfile.mkdtemp(prefix="omni-watermark-"))
        self.work.mkdir(parents=True, exist_ok=True)

    def _validate(self):
        if not Path(self.cfg.input).is_file():
            raise FileNotFoundError(self.cfg.input)
        if self.cfg.mode not in {"static", "dynamic"}:
            raise ValueError("mode must be static/dynamic")
        if self.cfg.engine not in {"fast", "ai"}:
            raise ValueError("engine must be fast/ai")
        if self.cfg.dynamic_backend not in {"opencv", "sam2", "yolo-world", "florence2"}:
            raise ValueError("unsupported dynamic backend")
        if self.cfg.engine == "ai" and not self.cfg.propainter_command:
            raise ValueError("--propainter-command is required when --engine ai")
        if self.cfg.batch_size < 1:
            raise ValueError("batch-size must be >= 1")
        for exe in ("ffmpeg", "ffprobe"):
            if shutil.which(exe) is None:
                raise OSError(f"{exe} is not on PATH")

    def probe(self):
        return ffmpeg.probe(self.cfg.input)

    def _extract(self):
        d = self.work / "frames"
        d.mkdir(exist_ok=True)
        cap = cv2.VideoCapture(self.cfg.input)
        if not cap.isOpened():
            raise OSError("Cannot decode input")
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        if fps <= 0:
            cap.release()
            raise RuntimeError("Invalid FPS")
        i = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if not cv2.imwrite(str(d / f"{i:08d}.png"), frame):
                    raise OSError("Frame write failed")
                i += 1
        finally:
            cap.release()
        if not i:
            raise RuntimeError("No frames extracted")
        return d, fps

    def _static_mask(self, d):
        files = sorted(d.glob("*.png"))
        stride = max(1, len(files) // 48)
        frames = [cv2.imread(str(p)) for p in files[::stride][:48]]
        frames = [frame for frame in frames if frame is not None]
        return StaticDetector(StaticDetectorConfig(dilate_px=self.cfg.mask_dilate)).detect(frames).mask

    def _dynamic_seed(self, d):
        files = sorted(d.glob("*.png"))
        frames = [cv2.imread(str(p)) for p in files[: min(12, len(files))]]
        frames = [frame for frame in frames if frame is not None]
        if not frames:
            raise RuntimeError("No frames available for dynamic detection")
        backend = OpenCVMotionBackend()
        tracker = IoUTracker()
        masks = []
        for frame in frames:
            tracks = tracker.update(backend.detect(frame))
            masks.append(merge_track_masks(tracks, frame.shape[:2]))
        seed = np.zeros_like(masks[0])
        for mask in masks:
            seed = cv2.bitwise_or(seed, mask)
        if self.cfg.mask_dilate > 0:
            k = 2 * self.cfg.mask_dilate + 1
            seed = cv2.dilate(seed, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        if not np.any(seed):
            raise RuntimeError("Dynamic detector produced an empty seed mask")
        return seed

    def _dynamic_masks(self, d):
        if self.cfg.dynamic_backend == "opencv":
            backend = OpenCVMotionBackend()
            tracker = IoUTracker()
            md = self.work / "masks"
            md.mkdir(exist_ok=True)
            for path in tqdm(sorted(d.glob("*.png")), desc="Dynamic masks"):
                frame = cv2.imread(str(path))
                if frame is None:
                    raise RuntimeError(f"Frame read failure: {path}")
                tracks = tracker.update(backend.detect(frame))
                mask = merge_track_masks(tracks, frame.shape[:2])
                if self.cfg.mask_dilate > 0:
                    k = 2 * self.cfg.mask_dilate + 1
                    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
                if not cv2.imwrite(str(md / path.name), mask):
                    raise OSError(f"Mask write failed: {path}")
            return md

        if self.cfg.dynamic_backend != "sam2":
            raise RuntimeError(
                f"{self.cfg.dynamic_backend} backend is not installed/configured yet"
            )
        device = self.cfg.device
        if device == "auto":
            device = "cuda" if self._cuda_available() else "cpu"
        backend = SAM2VideoBackend(
            SAM2Config(model_id=self.cfg.sam2_model_id, device=device)
        )
        try:
            propagated = backend.segment_video(self.cfg.input, self._dynamic_seed(d))
        finally:
            backend.close()
        md = self.work / "masks"
        md.mkdir(exist_ok=True)
        files = sorted(d.glob("*.png"))
        for idx, path in enumerate(tqdm(files, desc="SAM-2 masks")):
            mask = propagated.get(idx)
            if mask is None:
                frame = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if frame is None:
                    raise RuntimeError(f"Frame read failure: {path}")
                mask = np.zeros_like(frame)
            if self.cfg.mask_dilate > 0:
                k = 2 * self.cfg.mask_dilate + 1
                mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
            if not cv2.imwrite(str(md / path.name), mask):
                raise OSError(f"Mask write failed: {path}")
        return md

    @staticmethod
    def _cuda_available():
        try:
            import torch

            return torch.cuda.is_available()
        except ImportError:
            return False

    def _write_masks(self, d, mask):
        md = self.work / "masks"
        md.mkdir(exist_ok=True)
        for path in tqdm(sorted(d.glob("*.png")), desc="Masks"):
            if not cv2.imwrite(str(md / path.name), mask):
                raise OSError(f"Mask write failed: {path}")
        return md

    def _process_fast(self, d, md):
        out = self.work / "processed"
        out.mkdir(exist_ok=True)
        files = sorted(d.glob("*.png"))
        inpainter = Inpainter(
            "fast",
            InpaintConfig(self.cfg.telea_radius, self.cfg.batch_size, self.cfg.device),
        )
        for start in tqdm(range(0, len(files), self.cfg.batch_size), desc="Inpainting"):
            batch = files[start : start + self.cfg.batch_size]
            frames = [cv2.imread(str(path)) for path in batch]
            masks = [cv2.imread(str(md / path.name), cv2.IMREAD_GRAYSCALE) for path in batch]
            if any(item is None for item in frames + masks):
                raise RuntimeError("Frame/mask read failure")
            results = inpainter.process_batch(frames, masks)
            for path, image in zip(batch, results):
                if not cv2.imwrite(str(out / path.name), image):
                    raise OSError(f"Output frame write failed: {path}")
            inpainter.release_memory()
        return out

    def _process_ai(self, d, md, fps):
        files = sorted(d.glob("*.png"))
        frames = [cv2.imread(str(path), cv2.IMREAD_COLOR) for path in files]
        masks = [cv2.imread(str(md / path.name), cv2.IMREAD_GRAYSCALE) for path in files]
        if any(item is None for item in frames + masks):
            raise RuntimeError("Frame/mask read failure")
        backend = ProPainterBackend(
            self.cfg.propainter_command or (),
            work_dir=str(self.work),
            fp16=self.cfg.propainter_fp16,
            width=self.cfg.propainter_width,
            height=self.cfg.propainter_height,
            subvideo_length=self.cfg.propainter_subvideo_length,
            neighbor_length=self.cfg.propainter_neighbor_length,
            ref_stride=self.cfg.propainter_ref_stride,
        )
        results = backend.process(frames, masks, fps)
        out = self.work / "processed"
        out.mkdir(exist_ok=True)
        for path, image in zip(files, results):
            if not cv2.imwrite(str(out / path.name), image):
                raise OSError(f"Output frame write failed: {path}")
        return out

    def _assemble(self, out, fps):
        video_tmp = self.work / "video.mp4"
        (
            ffmpeg.input(str(out / "%08d.png"), framerate=fps, start_number=0)
            .output(str(video_tmp), vcodec="libx264", pix_fmt="yuv420p", movflags="+faststart")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        muxed = self.work / "muxed.mkv"
        try:
            (
                ffmpeg.output(
                    ffmpeg.input(str(video_tmp)).video,
                    ffmpeg.input(self.cfg.input).audio,
                    str(muxed),
                    vcodec="copy",
                    acodec="copy",
                    map_metadata=0,
                )
                .global_args("-loglevel", "error")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            os.replace(muxed, self.cfg.output)
        except ffmpeg.Error:
            os.replace(video_tmp, self.cfg.output)

    def run(self):
        d, fps = self._extract()
        if self.cfg.mode == "dynamic":
            masks = self._dynamic_masks(d)
        else:
            masks = self._write_masks(d, self._static_mask(d))
        out = self._process_ai(d, masks, fps) if self.cfg.engine == "ai" else self._process_fast(d, masks)
        self._assemble(out, fps)
        if not self.cfg.keep_temp and self.cfg.work_dir is None:
            shutil.rmtree(self.work, ignore_errors=True)
        return self.cfg.output

    async def run_async(self):
        return await asyncio.to_thread(self.run)
