from __future__ import annotations

import argparse
import sys

from .pipeline import PipelineConfig, VideoPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omni-watermark")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", choices=("static", "dynamic"), default="static")
    parser.add_argument("--engine", choices=("fast", "ai"), default="fast")
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--sample-rate", type=int, default=12)
    parser.add_argument("--mask-dilate", type=int, default=3)
    parser.add_argument("--telea-radius", type=int, default=3)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument(
        "--dynamic-backend",
        choices=("opencv", "sam2", "yolo-world", "florence2"),
        default="opencv",
        help="Dynamic mask backend.",
    )
    parser.add_argument(
        "--sam2-model-id",
        default="facebook/sam2.1-hiera-small",
        help="Hugging Face SAM 2 model ID.",
    )
    parser.add_argument(
        "--propainter-command",
        nargs="+",
        help="Command prefix for the installed ProPainter inference wrapper.",
    )
    parser.add_argument("--propainter-width", type=int)
    parser.add_argument("--propainter-height", type=int)
    parser.add_argument("--propainter-subvideo-length", type=int, default=80)
    parser.add_argument("--propainter-neighbor-length", type=int, default=10)
    parser.add_argument("--propainter-ref-stride", type=int, default=10)
    parser.add_argument(
        "--no-propainter-fp16",
        action="store_true",
        help="Disable ProPainter FP16 inference.",
    )
    parser.add_argument("--work-dir")
    parser.add_argument("--keep-temp", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = VideoPipeline(
            PipelineConfig(
                input=args.input,
                output=args.output,
                mode=args.mode,
                engine=args.engine,
                gpu_id=args.gpu_id,
                batch_size=args.batch_size,
                sample_rate=args.sample_rate,
                mask_dilate=args.mask_dilate,
                telea_radius=args.telea_radius,
                device=args.device,
                work_dir=args.work_dir,
                keep_temp=args.keep_temp,
                dynamic_backend=args.dynamic_backend,
                sam2_model_id=args.sam2_model_id,
                propainter_command=tuple(args.propainter_command) if args.propainter_command else None,
                propainter_fp16=not args.no_propainter_fp16,
                propainter_width=args.propainter_width,
                propainter_height=args.propainter_height,
                propainter_subvideo_length=args.propainter_subvideo_length,
                propainter_neighbor_length=args.propainter_neighbor_length,
                propainter_ref_stride=args.propainter_ref_stride,
            )
        ).run()
        print(f"Done: {output}")
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, RuntimeError, ValueError, MemoryError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
