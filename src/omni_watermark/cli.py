import argparse, sys
from .pipeline import PipelineConfig, VideoPipeline

def build_parser():
    p=argparse.ArgumentParser(prog="omni-watermark")
    p.add_argument("--input",required=True); p.add_argument("--output",required=True)
    p.add_argument("--mode",choices=("static","dynamic"),default="static")
    p.add_argument("--engine",choices=("fast","ai"),default="fast")
    p.add_argument("--gpu-id",type=int,default=0); p.add_argument("--batch-size",type=int,default=4)
    p.add_argument("--sample-rate",type=int,default=12); p.add_argument("--mask-dilate",type=int,default=3)
    p.add_argument("--telea-radius",type=int,default=3); p.add_argument("--device",choices=("auto","cpu","cuda"),default="auto")
    p.add_argument("--work-dir"); p.add_argument("--keep-temp",action="store_true"); return p

def main(argv=None):
    a=build_parser().parse_args(argv)
    try:
        out=VideoPipeline(PipelineConfig(input=a.input,output=a.output,mode=a.mode,engine=a.engine,gpu_id=a.gpu_id,batch_size=a.batch_size,sample_rate=a.sample_rate,mask_dilate=a.mask_dilate,telea_radius=a.telea_radius,device=a.device,work_dir=a.work_dir,keep_temp=a.keep_temp)).run()
        print(f"Done: {out}"); return 0
    except KeyboardInterrupt: return 130
    except Exception as e: print(f"ERROR: {e}",file=sys.stderr); return 1

if __name__=="__main__": raise SystemExit(main())
