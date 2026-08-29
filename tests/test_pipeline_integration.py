import shutil

import cv2
import numpy as np
import pytest

from omni_watermark.pipeline import PipelineConfig, VideoPipeline


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
def test_static_pipeline_end_to_end(tmp_path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "clean.mp4"

    width, height, fps, frames = 160, 120, 8, 8
    writer = cv2.VideoWriter(
        str(input_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    assert writer.isOpened()
    try:
        for index in range(frames):
            frame = np.full((height, width, 3), 80 + index * 2, dtype=np.uint8)
            cv2.rectangle(frame, (6, 6), (38, 28), (255, 255, 255), -1)
            writer.write(frame)
    finally:
        writer.release()

    result = VideoPipeline(
        PipelineConfig(
            input=str(input_path),
            output=str(output_path),
            mode="static",
            engine="fast",
            batch_size=2,
            sample_rate=4,
            mask_dilate=1,
            telea_radius=2,
        )
    ).run()

    assert result == str(output_path)
    assert output_path.is_file()
    assert output_path.stat().st_size > 0

    cap = cv2.VideoCapture(str(output_path))
    try:
        assert cap.isOpened()
        ok, frame = cap.read()
        assert ok
        assert frame is not None
        assert frame.shape[:2] == (height, width)
    finally:
        cap.release()
