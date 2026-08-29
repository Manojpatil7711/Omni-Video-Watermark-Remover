from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import ffmpeg
from tqdm import tqdm

from .detector import StaticDetector, StaticDetectorConfig
from .inpainter import InpaintConfig, Inpainter


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
    work_dir: Optional[str] = None


class VideoPipeline:
    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg
        self._validate()
        self.work = Path(
            cfg.work_dir or tempfile.mkdtemp(prefix="omni-watermark-")
        )
        self.work.mkdir(parents=True, exist_ok=True)

    def _validate(self):
        if not Path(self.cfg.input).is_file():
            raise FileNotFoundError(self.cfg.input)
        if self.cfg.mode not in {"static", "dynamic"}:
            raise ValueError("mode must be static/dynamic")
        if self.cfg.engine not in {"fast", "ai"}:
            raise ValueError("engine must be fast/ai")
        if self.cfg.batch_size < 1:
            raise ValueError("batch-size must be >= 1")
        for exe in ("ffmpeg", "ffprobe"):
            if shutil.which(exe) is None:
                raise EnvironmentError(f"{exe} is not on PATH")

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
                    raise IOError("Frame write failed")
                i += 1
        finally:
            cap.release()
        if not i:
            raise RuntimeError("No frames extracted")
        return d, fps

    def _static_mask(self, d):
        files = sorted(d.glob("*.png"))
        stride = max(1, len(files) // 48)
        frames = [
            cv2.imread(str(p)) for p in files[::stride][:48]
        ]
        frames = [frame for frame in frames if frame is not None]
        return StaticDetector(
            StaticDetectorConfig(dilate_px=self.cfg.mask_dilate)
        ).detect(frames).mask

    def _write_masks(self, d, mask):
        md = self.work / "masks"
        md.mkdir(exist_ok=True)
        for path in tqdm(sorted(d.glob("*.png")), desc="Masks"):
            if not cv2.imwrite(str(md / path.name), mask):
                raise IOError(f"Mask write failed: {path}")
        return md

    def _process(self, d, md):
        out = self.work / "processed"
        out.mkdir(exist_ok=True)
        files = sorted(d.glob("*.png"))
        inpainter = Inpainter(
            self.cfg.engine,
            InpaintConfig(
                self.cfg.telea_radius,
                self.cfg.batch_size,
                self.cfg.device,
            ),
        )
        for start in tqdm(
            range(0, len(files), self.cfg.batch_size), desc="Inpainting"
        ):
            batch = files[start : start + self.cfg.batch_size]
            frames = [cv2.imread(str(path)) for path in batch]
            masks = [
                cv2.imread(str(md / path.name), cv2.IMREAD_GRAYSCALE)
                for path in batch
            ]
            if any(item is None for item in frames + masks):
                raise RuntimeError("Frame/mask read failure")
            results = inpainter.process_batch(frames, masks)
            for path, image in zip(batch, results):
                if not cv2.imwrite(str(out / path.name), image):
                    raise IOError(f"Output frame write failed: {path}")
            inpainter.release_memory()
        return out

    def _assemble(self, out, fps):
        video_tmp = self.work / "video.mp4"
        (
            ffmpeg.input(str(out / "%08d.png"), framerate=fps, start_number=0)
            .output(
                str(video_tmp),
                vcodec="libx264",
                pix_fmt="yuv420p",
                movflags="+faststart",
            )
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
            raise NotImplementedError(
                "Dynamic mode requires configured detector/tracker + "
                "ProPainter/LaMa adapter"
            )
        masks = self._write_masks(d, self._static_mask(d))
        out = self._process(d, masks)
        self._assemble(out, fps)
        if not self.cfg.keep_temp and self.cfg.work_dir is None:
            shutil.rmtree(self.work, ignore_errors=True)
        return self.cfg.output

    async def run_async(self):
        return await asyncio.to_thread(self.run)
