import numpy as np

from omni_watermark.inpainter import FastInpainter


def test_empty_mask_identity():
    frame = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
    mask = np.zeros((32, 32), dtype=np.uint8)
    out = FastInpainter().inpaint(frame, mask)
    assert np.array_equal(frame, out)
